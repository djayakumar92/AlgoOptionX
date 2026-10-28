from __future__ import annotations

import logging
import os
from contextlib import closing
import sqlite3
import time
import uuid
from pathlib import Path

from algooptionx.research.storage.models import SCHEMA

logger = logging.getLogger(__name__)


class JournalMigrationError(RuntimeError):
    """An unsupported journal must be reconciled without discarding its history."""


_JOURNAL_TYPES = {
    "id": "INTEGER",
    "session_date": "TEXT",
    "trade_date": "TEXT",
    "option_type": "TEXT",
    "strike": "REAL",
    "entry_trigger": "REAL",
    "target": "REAL",
    "target_points": "REAL",
    "combined_signal": "TEXT",
    "outcome": "TEXT",
    "realized_points": "REAL",
    "created_ts": "INTEGER",
    "resolved_ts": "INTEGER",
}
_JOURNAL_NULLABLE = {
    "option_type",
    "strike",
    "entry_trigger",
    "target",
    "target_points",
    "realized_points",
    "resolved_ts",
}


def _journal_columns(conn: sqlite3.Connection) -> dict:
    obj = conn.execute(
        "SELECT type FROM sqlite_master WHERE name='journal_entries' COLLATE NOCASE"
    ).fetchone()
    if obj is None:
        return {}
    columns = {
        row["name"]: row for row in conn.execute("PRAGMA table_info(journal_entries)")
    }
    if (
        obj["type"] != "table"
        or not set(_JOURNAL_TYPES) <= columns.keys()
        or any(
            columns[name]["type"].upper() != kind
            for name, kind in _JOURNAL_TYPES.items()
        )
        or columns["id"]["pk"] != 1
        or any(column["pk"] for name, column in columns.items() if name != "id")
        or any(
            not columns[name]["notnull"]
            for name in (
                "session_date",
                "trade_date",
                "combined_signal",
                "outcome",
                "created_ts",
            )
        )
        or any(
            name not in {*_JOURNAL_TYPES, "note"}
            and column["notnull"]
            and column["dflt_value"] is None
            for name, column in columns.items()
        )
        or any(columns[name]["notnull"] for name in _JOURNAL_NULLABLE)
        or "note" in columns
        and (columns["note"]["type"].upper() != "TEXT" or columns["note"]["notnull"])
    ):
        raise JournalMigrationError(
            "Unsupported legacy journal schema. History was preserved. Back up the database "
            "and review a lossless schema/date mapping before starting research; no trade dates were inferred."
        )
    return columns


def _migrate_journal_entries_table(conn: sqlite3.Connection) -> None:
    """Only the known additive note upgrade is automatic; never DROP journal history."""
    columns = _journal_columns(conn)
    if not columns or "note" in columns:
        return
    if conn.in_transaction:
        raise JournalMigrationError(
            "Journal migration requires a dedicated connection outside a transaction."
        )
    database = next(
        row["file"]
        for row in conn.execute("PRAGMA database_list")
        if row["name"] == "main"
    )
    if not database:
        raise JournalMigrationError(
            "The additive journal migration requires a durable database backup."
        )
    try:
        # Exclude writers through BOTH snapshot and schema change. Backing up the
        # write connection itself here would block; use a separate committed reader.
        conn.execute("BEGIN IMMEDIATE")
        if "note" in _journal_columns(conn):
            conn.commit()
            return
        backup = Path(database + f".pre-journal-note-{uuid.uuid4().hex}.db")
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        with closing(
            sqlite3.connect(Path(database).as_uri() + "?mode=ro", uri=True, timeout=15)
        ) as source:
            with closing(sqlite3.connect(backup)) as destination:
                source.backup(destination)
                if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise JournalMigrationError(
                        "Journal backup failed verification; no migration was applied."
                    )
        conn.execute("ALTER TABLE journal_entries ADD COLUMN note TEXT")
        conn.execute("""CREATE TABLE IF NOT EXISTS algooptionx_schema_migrations (
            id TEXT PRIMARY KEY, applied_ts INTEGER NOT NULL, backup_file TEXT NOT NULL)""")
        conn.execute(
            "INSERT INTO algooptionx_schema_migrations VALUES(?,?,?)",
            ("journal-note-v1", int(time.time()), backup.name),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


# Columns added to ledger tables after their first release. CREATE TABLE IF
# NOT EXISTS never alters an existing table, so a column added to SCHEMA is
# invisible to any database created before it -- which is how the first
# version of this shipped and immediately failed with "no such column". Adding
# a column here is the whole migration: SQLite's ALTER TABLE ADD COLUMN is
# cheap and non-destructive. Journal upgrades above also preserve all rows.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "daily_features": {"atm_iv": "REAL"},
}


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    for table, columns in _ADDED_COLUMNS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue  # table doesn't exist yet -- SCHEMA is about to create it in full
        for name, decl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
                logger.info("Added missing column %s.%s", table, name)
    conn.commit()


def connect(db_path: Path, retention_days: int | None = None) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        # Validate before changing journal mode, creating tables or applying retention.
        _migrate_journal_entries_table(conn)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(SCHEMA)
        _add_missing_columns(conn)
        conn.commit()
    except BaseException:
        conn.close()
        raise

    if retention_days is not None:
        # Local import -- repository.py doesn't import db.py, so no cycle,
        # but keeping it here (rather than a module-level import) makes clear
        # this is the one place db.py reaches into repository, not a general
        # dependency between the two modules.
        from algooptionx.research.storage import repository

        cutoff_ts = int(time.time()) - retention_days * 86400
        deleted = repository.prune_option_chain_snapshots(conn, cutoff_ts)
        if deleted:
            logger.info(
                "Pruned %d option_chain_snapshot rows older than %d days",
                deleted,
                retention_days,
            )

    return conn

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from algooptionx.research.storage.models import SCHEMA

logger = logging.getLogger(__name__)


def _migrate_journal_entries_table(conn: sqlite3.Connection) -> None:
    """journal_entries was added pre-release and changed shape once (nullable
    leg columns + a new `note` column, to support NO_TRADE/sit-out rows).
    CREATE TABLE IF NOT EXISTS in SCHEMA won't alter an already-created table,
    so drop and let SCHEMA recreate it if it's still the old shape. Safe at
    this stage -- this table has no real trading history in it yet, only
    entries created during this feature's own development/testing."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(journal_entries)")}
    if cols and ("note" not in cols or "trade_date" not in cols):
        conn.execute("DROP TABLE journal_entries")
        conn.commit()


# Columns added to ledger tables after their first release. CREATE TABLE IF
# NOT EXISTS never alters an existing table, so a column added to SCHEMA is
# invisible to any database created before it -- which is how the first
# version of this shipped and immediately failed with "no such column". Adding
# a column here is the whole migration: SQLite's ALTER TABLE ADD COLUMN is
# cheap and non-destructive, and unlike the journal_entries migration above it
# does not throw away rows.
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
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    _migrate_journal_entries_table(conn)
    conn.executescript(SCHEMA)
    _add_missing_columns(conn)
    conn.commit()

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
                "Pruned %d option_chain_snapshot rows older than %d days", deleted, retention_days
            )

    return conn

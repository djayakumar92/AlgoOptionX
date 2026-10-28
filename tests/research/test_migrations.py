"""Historical journal rows must survive supported upgrades and unsupported schemas."""

import sqlite3
import os
import shutil
from concurrent.futures import ThreadPoolExecutor

import pytest

from algooptionx.research.storage.db import (
    JournalMigrationError,
    _migrate_journal_entries_table,
    connect,
)
from algooptionx.research.storage.models import SCHEMA


def fixture_db(path, *, note=False, trade_date=True, constrained=False):
    schema = SCHEMA
    if not note:
        schema = schema.replace(
            "    note             TEXT,               -- build_trade_plan()'s reasoning, e.g. why it sat out\n",
            "",
        )
    if not trade_date:
        schema = schema.replace(
            "    trade_date       TEXT    NOT NULL,   -- ISO date, the NEXT trading session this plan is meant to be acted on\n",
            "",
        ).replace(
            "CREATE INDEX IF NOT EXISTS idx_journal_entries_trade_date ON journal_entries (trade_date);",
            "",
        )
    if constrained:
        schema = schema.replace(
            "    option_type      TEXT,", "    option_type      TEXT NOT NULL,"
        )
    with sqlite3.connect(path) as c:
        c.executescript(schema)
        cols = "id, session_date, option_type, combined_signal, outcome, realized_points, created_ts"
        values = [41, "2026-10-28", "CE", "Mixed", "STOP_HIT", -5.25, 123]
        if trade_date:
            cols += ", trade_date"
            values.append("2026-10-29")
        c.execute(
            f"INSERT INTO journal_entries ({cols}) VALUES ({','.join('?' for _ in values)})",
            values,
        )
        c.execute("ALTER TABLE journal_entries ADD COLUMN user_extra TEXT")
        c.execute("UPDATE journal_entries SET user_extra='retain me'")


def journal(path):
    with sqlite3.connect(path) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("SELECT * FROM journal_entries ORDER BY id")]


def test_supported_additive_migration_preserves_rows_backup_and_version(tmp_path):
    p = tmp_path / "legacy.db"
    fixture_db(p)
    before = journal(p)
    c = connect(p)
    try:
        after = [dict(r) for r in c.execute("SELECT * FROM journal_entries")]
        assert after == [dict(before[0], note=None)]
        marker = c.execute("SELECT * FROM algooptionx_schema_migrations").fetchone()
        assert marker["id"] == "journal-note-v1"
        backup = p.parent / marker["backup_file"]
        assert journal(backup) == before
        if os.name == "posix":
            assert backup.stat().st_mode & 0o777 == 0o600
        restored = tmp_path / "restored.db"
        shutil.copy2(backup, restored)
        assert journal(restored) == before
        with sqlite3.connect(restored) as restored_conn:
            assert restored_conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        c.execute(
            "INSERT INTO journal_entries(session_date,trade_date,combined_signal,created_ts) VALUES('2026-10-28','2026-10-29','NO_TRADE',200)"
        )
        c.commit()
    finally:
        c.close()
    again = connect(p)
    assert again.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0] == 2
    assert len(list(tmp_path.glob("*.pre-journal-note-*.db"))) == 1
    again.close()


@pytest.mark.parametrize("trade_date,constrained", [(False, False), (True, True)])
def test_unsupported_schema_refuses_without_loss_or_schema_changes(
    tmp_path, trade_date, constrained
):
    p = tmp_path / "legacy.db"
    fixture_db(p, trade_date=trade_date, constrained=constrained)
    before = journal(p)
    with sqlite3.connect(p) as c:
        schema_before = c.execute(
            "SELECT type,name,sql FROM sqlite_master ORDER BY name"
        ).fetchall()
        mode_before = c.execute("PRAGMA journal_mode").fetchone()[0]
    with pytest.raises(JournalMigrationError, match="History was preserved"):
        connect(p, retention_days=0)
    assert journal(p) == before
    with sqlite3.connect(p) as c:
        assert (
            c.execute(
                "SELECT type,name,sql FROM sqlite_master ORDER BY name"
            ).fetchall()
            == schema_before
        )
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == mode_before
    assert not list(tmp_path.glob("*.pre-journal-note-*.db"))


def test_interrupted_additive_migration_rolls_back_and_keeps_backup(tmp_path):
    p = tmp_path / "legacy.db"
    fixture_db(p)
    before = journal(p)
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row

    def authorize(action, name, *_):
        return (
            sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_CREATE_TABLE
            and name == "algooptionx_schema_migrations"
            else sqlite3.SQLITE_OK
        )

    c.set_authorizer(authorize)
    with pytest.raises(sqlite3.DatabaseError):
        _migrate_journal_entries_table(c)
    c.close()
    assert journal(p) == before
    backups = list(tmp_path.glob("*.pre-journal-note-*.db"))
    assert len(backups) == 1 and journal(backups[0]) == before
    c = connect(p)
    assert c.execute("SELECT note FROM journal_entries").fetchone()[0] is None
    c.close()


def test_current_and_fresh_database_need_no_migration_backup(tmp_path):
    p = tmp_path / "current.db"
    fixture_db(p, note=True)
    before = journal(p)
    c = connect(p)
    c.close()
    assert journal(p) == before
    c = connect(tmp_path / "fresh.db")
    assert c.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0] == 0
    c.close()
    assert not list(tmp_path.glob("*.pre-journal-note-*.db"))


def test_backup_excludes_writers_until_upgrade_commits(tmp_path, monkeypatch):
    from algooptionx.research.storage import db

    p = tmp_path / "legacy.db"
    fixture_db(p)
    real_connect = sqlite3.connect
    attempts = []

    def competing_write():
        with real_connect(p, timeout=0.05) as writer:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                writer.execute("UPDATE journal_entries SET outcome='CORRUPTED'")
        attempts.append("writer excluded")

    class Snapshot(sqlite3.Connection):
        def backup(self, target, *args, **kwargs):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(competing_write).result(timeout=5)
            return super().backup(target, *args, **kwargs)

    def connect_wrapper(*args, **kwargs):
        if kwargs.get("uri"):
            kwargs["factory"] = Snapshot
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(db.sqlite3, "connect", connect_wrapper)
    c = connect(p)
    c.close()
    assert attempts == ["writer excluded"]
    assert journal(p)[0]["outcome"] == "STOP_HIT"


def test_unknown_required_extra_column_is_refused_without_change(tmp_path):
    p = tmp_path / "legacy.db"
    fixture_db(p)
    with sqlite3.connect(p) as c:
        c.execute("DELETE FROM journal_entries")
        c.execute(
            "ALTER TABLE journal_entries ADD COLUMN unknown_required TEXT NOT NULL"
        )
    with pytest.raises(JournalMigrationError):
        connect(p)
    assert journal(p) == []
    assert not list(tmp_path.glob("*.pre-journal-note-*.db"))


def test_composite_journal_primary_key_is_unsupported(tmp_path):
    p = tmp_path / "composite.db"
    definition = SCHEMA.split("CREATE TABLE IF NOT EXISTS journal_entries (", 1)[
        1
    ].split(");", 1)[0]
    definition = definition.replace(
        "id               INTEGER PRIMARY KEY AUTOINCREMENT,", "id INTEGER,"
    )
    with sqlite3.connect(p) as c:
        c.execute(
            "CREATE TABLE journal_entries ("
            + definition
            + ", PRIMARY KEY(id, trade_date))"
        )
        before = c.execute(
            "SELECT sql FROM sqlite_master WHERE name='journal_entries'"
        ).fetchone()[0]
    with pytest.raises(JournalMigrationError):
        connect(p)
    with sqlite3.connect(p) as c:
        assert (
            c.execute(
                "SELECT sql FROM sqlite_master WHERE name='journal_entries'"
            ).fetchone()[0]
            == before
        )


def test_case_variant_unsupported_journal_is_not_missed(tmp_path):
    p = tmp_path / "legacy.db"
    with sqlite3.connect(p) as c:
        c.execute(
            "CREATE TABLE JOURNAL_ENTRIES(id INTEGER PRIMARY KEY, legacy_value TEXT)"
        )
        c.execute("INSERT INTO JOURNAL_ENTRIES VALUES(1,'keep')")
    with pytest.raises(JournalMigrationError, match="History was preserved"):
        connect(p)
    with sqlite3.connect(p) as c:
        assert c.execute("SELECT * FROM JOURNAL_ENTRIES").fetchall() == [(1, "keep")]
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "delete"

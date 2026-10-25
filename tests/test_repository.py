import sqlite3

from dhan_analyzer.storage import repository
from dhan_analyzer.storage.models import SCHEMA


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _insert(conn, trade_date, option_type, outcome, realized_points):
    conn.execute(
        """
        INSERT INTO journal_entries
            (session_date, trade_date, option_type, strike, entry_trigger, target, target_points,
             combined_signal, note, outcome, realized_points, created_ts)
        VALUES ('2026-09-01', ?, ?, 24000, 50, 40, 10, 'Mixed', NULL, ?, ?, 0)
        """,
        (trade_date, option_type, outcome, realized_points),
    )
    conn.commit()


def test_get_most_recent_graded_day_none_when_all_pending():
    conn = _conn()
    _insert(conn, "2026-09-01", "CE", "PENDING", None)
    assert repository.get_most_recent_graded_day(conn) is None


def test_get_most_recent_graded_day_sums_both_legs_on_the_same_date():
    conn = _conn()
    _insert(conn, "2026-09-01", "CE", "STOP_HIT", -0.65)
    _insert(conn, "2026-09-01", "PE", "STOP_HIT", -10.15)
    assert repository.get_most_recent_graded_day(conn) == ("2026-09-01", -10.8)


def test_get_most_recent_graded_day_picks_latest_date_not_highest_id():
    conn = _conn()
    _insert(conn, "2026-09-01", "CE", "STOP_HIT", -5.0)
    _insert(conn, "2026-09-02", None, "NO_TRADE", None)
    trade_date, total = repository.get_most_recent_graded_day(conn)
    assert trade_date == "2026-09-02"
    assert total == 0.0  # NULL realized_points on a NO_TRADE day counts as 0, not skipped


def test_get_most_recent_graded_day_ignores_pending_rows_on_a_later_date():
    conn = _conn()
    _insert(conn, "2026-09-01", "CE", "TARGET_HIT", 8.0)
    _insert(conn, "2026-09-02", "PE", "PENDING", None)  # today's plan, not graded yet
    trade_date, total = repository.get_most_recent_graded_day(conn)
    assert trade_date == "2026-09-01"
    assert total == 8.0


def test_get_journal_entries_in_range_filters_dates_and_excludes_pending():
    conn = _conn()
    _insert(conn, "2026-08-30", "CE", "TARGET_HIT", 5.0)  # before range
    _insert(conn, "2026-09-01", "CE", "STOP_HIT", -3.0)
    _insert(conn, "2026-09-02", "PE", "PENDING", None)  # in range but not graded yet
    _insert(conn, "2026-09-05", "CE", "TARGET_HIT", 7.0)  # after range
    rows = repository.get_journal_entries_in_range(conn, "2026-09-01", "2026-09-02")
    assert len(rows) == 1
    assert rows[0]["trade_date"] == "2026-09-01"


def test_get_journal_entries_in_range_chronological_order():
    conn = _conn()
    _insert(conn, "2026-09-03", "CE", "TARGET_HIT", 1.0)
    _insert(conn, "2026-09-01", "CE", "TARGET_HIT", 2.0)
    _insert(conn, "2026-09-02", "CE", "TARGET_HIT", 3.0)
    rows = repository.get_journal_entries_in_range(conn, "2026-09-01", "2026-09-03")
    assert [r["trade_date"] for r in rows] == ["2026-09-01", "2026-09-02", "2026-09-03"]


def test_insert_and_get_backtest_runs():
    conn = _conn()
    run_id = repository.insert_backtest_run(conn, {
        "start_date": "2026-08-01", "end_date": "2026-08-31", "status": "DONE",
        "created_ts": 1000, "completed_ts": 1100, "total_days": 20,
        "graded_trades": 15, "no_trade_days": 5, "not_triggered": 0,
        "net_points": 42.5, "win_rate": 0.6, "profit_factor": 1.8,
        "expectancy_points": 2.8, "avg_r": 0.3, "max_drawdown_points": 12.0,
        "largest_win": 15.0, "largest_loss": -8.0, "max_consecutive_losses": 2,
        "error": None,
    })
    assert run_id > 0
    runs = repository.get_backtest_runs(conn)
    assert len(runs) == 1
    assert runs[0]["net_points"] == 42.5
    assert runs[0]["status"] == "DONE"

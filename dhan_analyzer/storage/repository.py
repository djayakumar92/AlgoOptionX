from __future__ import annotations

import functools
import json
import sqlite3
import threading
from datetime import date, datetime, time

import pandas as pd

# sqlite3.Connection is shared across threads (db.connect() sets
# check_same_thread=False) -- the Live worker, HLC worker, and now request
# handler threads (GET /api/journal/entries) can all call in here concurrently.
# A bare Connection object isn't safe for truly simultaneous calls from
# different threads (hit live as "sqlite3.InterfaceError: bad parameter or
# other API misuse" once journal routes started reading conn directly), so
# every function below is serialized through this one lock. RLock, not Lock --
# get_latest_two_snapshots() calls get_snapshot_at() directly, both wrapped,
# which would deadlock a plain Lock on the same thread.
_DB_LOCK = threading.RLock()


def _locked(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _DB_LOCK:
            return fn(*args, **kwargs)

    return wrapper


# ---- candles -----------------------------------------------------------

@_locked
def upsert_candles(conn: sqlite3.Connection, symbol: str, interval: str, rows: list[dict]) -> None:
    """rows: dicts with keys ts, open, high, low, close, volume, oi (oi optional).

    Idempotent: re-running a backfill over an already-stored range is a no-op for
    existing rows, which is what makes startup catch-up safe to call unconditionally.
    """
    conn.executemany(
        """
        INSERT INTO candles (symbol, interval, ts, open, high, low, close, volume, oi)
        VALUES (:symbol, :interval, :ts, :open, :high, :low, :close, :volume, :oi)
        ON CONFLICT(symbol, interval, ts) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume, oi=excluded.oi
        """,
        [{"symbol": symbol, "interval": interval, "oi": None, **row} for row in rows],
    )
    conn.commit()


@_locked
def last_candle_ts(conn: sqlite3.Connection, symbol: str, interval: str) -> int | None:
    row = conn.execute(
        "SELECT MAX(ts) AS max_ts FROM candles WHERE symbol = ? AND interval = ?",
        (symbol, interval),
    ).fetchone()
    return row["max_ts"] if row and row["max_ts"] is not None else None


@_locked
def get_candles(conn: sqlite3.Connection, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
    df = pd.read_sql_query(
        """
        SELECT * FROM candles WHERE symbol = ? AND interval = ?
        ORDER BY ts DESC LIMIT ?
        """,
        conn,
        params=(symbol, interval, limit),
    )
    return df.iloc[::-1].reset_index(drop=True)


@_locked
def get_close_on_date(conn: sqlite3.Connection, symbol: str, interval: str, session_date: date) -> float | None:
    """Last candle's close for symbol/interval on session_date, or None if none stored."""
    start_ts = int(datetime.combine(session_date, time.min).timestamp())
    end_ts = int(datetime.combine(session_date, time.max).timestamp())
    row = conn.execute(
        """
        SELECT close FROM candles WHERE symbol = ? AND interval = ? AND ts BETWEEN ? AND ?
        ORDER BY ts DESC LIMIT 1
        """,
        (symbol, interval, start_ts, end_ts),
    ).fetchone()
    return row["close"] if row else None


# ---- option chain snapshots ---------------------------------------------

@_locked
def insert_option_chain_snapshot(
    conn: sqlite3.Connection,
    underlying: str,
    expiry: date,
    ts: int,
    rows: list[dict],
) -> None:
    """rows: one dict per (strike, option_type) with the fields in the schema."""
    conn.executemany(
        """
        INSERT INTO option_chain_snapshot
            (underlying, expiry, strike, option_type, ts, ltp, oi, prev_day_oi,
             volume, iv, delta, theta, gamma, vega, bid, ask, bid_qty, ask_qty)
        VALUES
            (:underlying, :expiry, :strike, :option_type, :ts, :ltp, :oi, :prev_day_oi,
             :volume, :iv, :delta, :theta, :gamma, :vega, :bid, :ask, :bid_qty, :ask_qty)
        """,
        [
            {"underlying": underlying, "expiry": expiry.isoformat(), "ts": ts, **row}
            for row in rows
        ],
    )
    conn.commit()


@_locked
def prune_option_chain_snapshots(conn: sqlite3.Connection, cutoff_ts: int) -> int:
    """Delete snapshot rows older than cutoff_ts (epoch seconds). Nothing in
    this app reads option_chain_snapshot beyond the current session (see
    get_oi_timeseries) or the last couple of polls (get_latest_two_snapshots)
    -- this table only exists as an ever-growing poll log otherwise, and had
    reached ~4 million rows with no cleanup ever having run. Called once at
    startup (see db.connect), not on a timer -- this app restarts at least
    once per trading day, which is enough cadence for a housekeeping task."""
    cur = conn.execute("DELETE FROM option_chain_snapshot WHERE ts < ?", (cutoff_ts,))
    conn.commit()
    return cur.rowcount


@_locked
def latest_snapshot_ts(conn: sqlite3.Connection, underlying: str, expiry: date) -> int | None:
    row = conn.execute(
        "SELECT MAX(ts) AS max_ts FROM option_chain_snapshot WHERE underlying = ? AND expiry = ?",
        (underlying, expiry.isoformat()),
    ).fetchone()
    return row["max_ts"] if row and row["max_ts"] is not None else None


@_locked
def get_snapshot_at(conn: sqlite3.Connection, underlying: str, expiry: date, ts: int) -> pd.DataFrame:
    return pd.read_sql_query(
        """
        SELECT * FROM option_chain_snapshot
        WHERE underlying = ? AND expiry = ? AND ts = ?
        """,
        conn,
        params=(underlying, expiry.isoformat(), ts),
    )


@_locked
def get_oi_timeseries(
    conn: sqlite3.Connection, underlying: str, expiry: date, since_ts: int, bucket_seconds: int = 300
) -> list[dict]:
    """Total CE/PE OI (summed across all strikes) at one representative poll
    per bucket_seconds-wide bucket, from since_ts onward -- for the OI-over-
    time chart. Every poll already stores the full chain (scheduler.py), so
    this is a query over existing data, not new ingestion.

    Picks the *last* snapshot's OI within each bucket (not a sum/average
    across the ~85 polls a 5-minute bucket contains at the default 3.5s poll
    cadence -- OI is a point-in-time reading, not something to accumulate).

    Two queries, not one CTE+JOIN: with option_chain_snapshot at millions of
    rows (no retention policy yet -- every poll since the app started, see
    the project's own notes on this), SQLite's planner picked a nested-loop
    join for the single-query version that took minutes instead of
    milliseconds (confirmed live via EXPLAIN QUERY PLAN -- it stopped using
    the ts index for the join side). An IN-list lookup against the small
    picked-timestamp set is the pattern SQLite optimizes well here; the
    per-bucket sum is cheap to do in Python over the resulting handful of
    rows (buckets x strikes x 2, a few thousand rows at most for a full
    session, not millions)."""
    bucket_rows = conn.execute(
        """
        SELECT (ts / ?) * ? AS bucket_ts, MAX(ts) AS rep_ts
        FROM option_chain_snapshot
        WHERE underlying = ? AND expiry = ? AND ts >= ?
        GROUP BY bucket_ts
        ORDER BY bucket_ts
        """,
        (bucket_seconds, bucket_seconds, underlying, expiry.isoformat(), since_ts),
    ).fetchall()
    if not bucket_rows:
        return []

    rep_ts_list = [row["rep_ts"] for row in bucket_rows]
    placeholders = ",".join("?" * len(rep_ts_list))
    detail_rows = conn.execute(
        f"""
        SELECT ts, option_type, oi FROM option_chain_snapshot
        WHERE underlying = ? AND expiry = ? AND ts IN ({placeholders})
        """,
        (underlying, expiry.isoformat(), *rep_ts_list),
    ).fetchall()

    totals_by_ts: dict[int, dict[str, int]] = {ts: {"CE": 0, "PE": 0} for ts in rep_ts_list}
    for row in detail_rows:
        if row["oi"] is not None and row["option_type"] in totals_by_ts.get(row["ts"], {}):
            totals_by_ts[row["ts"]][row["option_type"]] += row["oi"]

    return [
        {"ts": bucket["bucket_ts"], "ce_oi": totals_by_ts[bucket["rep_ts"]]["CE"], "pe_oi": totals_by_ts[bucket["rep_ts"]]["PE"]}
        for bucket in bucket_rows
    ]


@_locked
def get_latest_two_snapshots(
    conn: sqlite3.Connection, underlying: str, expiry: date
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Returns (latest, previous) snapshot DataFrames for OI-delta based signals.

    previous is None if only one snapshot has been recorded yet.
    """
    ts_rows = conn.execute(
        """
        SELECT DISTINCT ts FROM option_chain_snapshot
        WHERE underlying = ? AND expiry = ?
        ORDER BY ts DESC LIMIT 2
        """,
        (underlying, expiry.isoformat()),
    ).fetchall()

    if not ts_rows:
        return pd.DataFrame(), None

    latest = get_snapshot_at(conn, underlying, expiry, ts_rows[0]["ts"])
    if len(ts_rows) < 2:
        return latest, None

    previous = get_snapshot_at(conn, underlying, expiry, ts_rows[1]["ts"])
    return latest, previous


# ---- signals log ----------------------------------------------------------

@_locked
def log_signal(conn: sqlite3.Connection, underlying: str, suggestion) -> None:
    """suggestion: dhan_analyzer.signals.combine.Suggestion"""
    conn.execute(
        """
        INSERT INTO signals_log
            (ts, underlying, bias, confidence, suggested_instrument,
             entry_zone, stop_loss, watch_level, rationale, signals_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(datetime.now().timestamp()),
            underlying,
            suggestion.bias,
            suggestion.confidence,
            suggestion.suggested_instrument,
            suggestion.entry_zone,
            suggestion.stop_loss,
            suggestion.watch_level,
            suggestion.rationale,
            json.dumps(suggestion.contributing_signals),
        ),
    )
    conn.commit()


# ---- journal ----------------------------------------------------------

@_locked
def insert_journal_entry(
    conn: sqlite3.Connection,
    session_date: str,
    trade_date: str,
    option_type: str,
    strike: float,
    entry_trigger: float,
    target: float,
    target_points: float,
    combined_signal: str,
    note: str,
) -> int:
    """One row per planned leg (build_trade_plan() may produce up to
    max_trades_per_day of these for one trade_date). Starts PENDING -- graded
    once trade_date's own session is confirmed complete (a later HLC cycle
    resolves session_date == this row's trade_date), see hlc_worker.py /
    journal_grading.py. session_date is just the basis the numbers came from
    (the *previous* completed session, not the day the plan is acted on)."""
    cur = conn.execute(
        """
        INSERT INTO journal_entries
            (session_date, trade_date, option_type, strike, entry_trigger, target, target_points,
             combined_signal, note, outcome, created_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
        """,
        (
            session_date, trade_date, option_type, strike, entry_trigger, target, target_points,
            combined_signal, note, int(datetime.now().timestamp()),
        ),
    )
    conn.commit()
    return cur.lastrowid


@_locked
def insert_no_trade_entry(
    conn: sqlite3.Connection, session_date: str, trade_date: str, combined_signal: str, note: str
) -> int:
    """A sit-out day (build_trade_plan() produced no legs) still gets one row,
    so the Journal shows every session it looked at, not silent gaps that look
    like the app just didn't run that day. Resolved immediately -- there's
    nothing to grade."""
    cur = conn.execute(
        """
        INSERT INTO journal_entries
            (session_date, trade_date, combined_signal, note, outcome, created_ts, resolved_ts)
        VALUES (?, ?, ?, ?, 'NO_TRADE', ?, ?)
        """,
        (
            session_date, trade_date, combined_signal, note,
            int(datetime.now().timestamp()), int(datetime.now().timestamp()),
        ),
    )
    conn.commit()
    return cur.lastrowid


@_locked
def has_journal_entries_for_trade_date(conn: sqlite3.Connection, trade_date: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM journal_entries WHERE trade_date = ? LIMIT 1", (trade_date,)
    ).fetchone()
    return row is not None


@_locked
def get_pending_journal_entries(conn: sqlite3.Connection, trade_date: str) -> list[sqlite3.Row]:
    """Entries whose plan was meant to be traded on trade_date -- graded once
    trade_date's own session is confirmed complete."""
    return conn.execute(
        "SELECT * FROM journal_entries WHERE trade_date = ? AND outcome = 'PENDING'",
        (trade_date,),
    ).fetchall()


@_locked
def update_journal_outcome(conn: sqlite3.Connection, entry_id: int, outcome: str, realized_points: float | None) -> None:
    conn.execute(
        "UPDATE journal_entries SET outcome = ?, realized_points = ?, resolved_ts = ? WHERE id = ?",
        (outcome, realized_points, int(datetime.now().timestamp()), entry_id),
    )
    conn.commit()


@_locked
def get_most_recent_graded_day(conn: sqlite3.Connection) -> tuple[str, float] | None:
    """(trade_date, total realized_points that day) for the most recently
    *graded* trading day -- i.e. the latest trade_date where at least one
    entry has left PENDING, summed across every leg that day (a Strong
    Bearish day sells both CE and PE, each its own row). None if nothing has
    been graded yet. Untriggered/no-trade legs contribute 0, not NULL."""
    row = conn.execute(
        "SELECT MAX(trade_date) AS trade_date FROM journal_entries WHERE outcome != 'PENDING'"
    ).fetchone()
    trade_date = row["trade_date"] if row else None
    if trade_date is None:
        return None
    total = conn.execute(
        "SELECT COALESCE(SUM(realized_points), 0) AS total FROM journal_entries WHERE trade_date = ? AND outcome != 'PENDING'",
        (trade_date,),
    ).fetchone()["total"]
    return trade_date, float(total)


@_locked
def get_journal_entries(conn: sqlite3.Connection, limit: int = 30) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM journal_entries ORDER BY trade_date DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()


@_locked
def get_journal_entries_in_range(conn: sqlite3.Connection, start_trade_date: str, end_trade_date: str) -> list[sqlite3.Row]:
    """Every non-PENDING entry whose trade_date falls in [start, end] (both
    ISO dates, inclusive), oldest first -- feeds backtest_stats.compute_stats,
    which needs chronological order for drawdown/streak calculations."""
    return conn.execute(
        """
        SELECT * FROM journal_entries
        WHERE trade_date BETWEEN ? AND ? AND outcome != 'PENDING'
        ORDER BY trade_date ASC, id ASC
        """,
        (start_trade_date, end_trade_date),
    ).fetchall()


@_locked
def insert_backtest_run(conn: sqlite3.Connection, row: dict) -> int:
    """row keys match backtest_runs' columns (minus id) -- see
    backtest_worker.py for what populates it."""
    cols = list(row.keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    cur = conn.execute(
        f"INSERT INTO backtest_runs ({', '.join(cols)}) VALUES ({placeholders})", row
    )
    conn.commit()
    return cur.lastrowid


@_locked
def get_backtest_runs(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM backtest_runs ORDER BY created_ts DESC LIMIT ?", (limit,)
    ).fetchall()


# ---- learning ledger ---------------------------------------------------
#
# Backing store for signals/ledger.py and signals/calibration.py. Kept here
# with the rest of the SQL rather than in the signals package so the signals
# modules stay pure functions over data, as they are everywhere else.


@_locked
def upsert_daily_features(conn: sqlite3.Connection, row: dict) -> None:
    """One row per trading session, written twice: once at decision time with
    the engine's read, once after the close with what the market did. Both
    writes go through here, and a later write only overwrites the columns it
    actually supplies -- so the end-of-day OHLC update can't blank out the
    morning's regime read (and vice versa)."""
    cols = [c for c in row if c != "trade_date"]
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols)
    placeholders = ", ".join(f":{c}" for c in row)
    conn.execute(
        f"INSERT INTO daily_features ({', '.join(row)}) VALUES ({placeholders}) "
        f"ON CONFLICT(trade_date) DO UPDATE SET {updates}",
        row,
    )
    conn.commit()


@_locked
def get_daily_features(conn: sqlite3.Connection, limit: int = 120) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM daily_features ORDER BY trade_date DESC LIMIT ?", (limit,)
    ).fetchall()


@_locked
def record_setup_event(conn: sqlite3.Connection, row: dict) -> int | None:
    """Insert one armed-setup event. Returns the new row id, or None if this
    setup was already recorded for this trade_date.

    The dedupe is the point: the engine re-evaluates on every poll, so
    without the UNIQUE(trade_date, setup_key) guard a single armed setup
    would write hundreds of identical rows and quietly inflate every hit-rate
    denominator computed from this table."""
    cols = list(row.keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    cur = conn.execute(
        f"INSERT OR IGNORE INTO setup_events ({', '.join(cols)}) VALUES ({placeholders})", row
    )
    conn.commit()
    return cur.lastrowid if cur.rowcount else None


@_locked
def get_setup_events_for_date(conn: sqlite3.Connection, trade_date: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM setup_events WHERE trade_date = ? ORDER BY armed_ts", (trade_date,)
    ).fetchall()


@_locked
def get_ungraded_setup_events(conn: sqlite3.Connection, before_trade_date: str) -> list[sqlite3.Row]:
    """Armed events from sessions that have already finished but have no
    outcome row yet -- the work queue for the end-of-day grading pass."""
    return conn.execute(
        """
        SELECT e.* FROM setup_events e
        LEFT JOIN setup_outcomes o ON o.event_id = e.id
        WHERE o.event_id IS NULL AND e.trade_date < ?
        ORDER BY e.trade_date, e.armed_ts
        """,
        (before_trade_date,),
    ).fetchall()


@_locked
def record_setup_outcome(conn: sqlite3.Connection, row: dict) -> None:
    cols = list(row.keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    conn.execute(
        f"INSERT OR REPLACE INTO setup_outcomes ({', '.join(cols)}) VALUES ({placeholders})", row
    )
    conn.commit()


@_locked
def get_setup_outcomes(conn: sqlite3.Connection, setup_key: str | None = None) -> list[sqlite3.Row]:
    """Graded outcomes joined to their event, so calibration can slice by the
    regime context that was live when the setup armed."""
    sql = """
        SELECT o.*, e.score, e.grade, e.side, e.action, e.structure_regime,
               e.day_type, e.premium_pricing, e.gamma_regime, e.session_window,
               e.is_expiry_day
        FROM setup_outcomes o
        JOIN setup_events e ON e.id = o.event_id
    """
    params: tuple = ()
    if setup_key:
        sql += " WHERE o.setup_key = ?"
        params = (setup_key,)
    sql += " ORDER BY o.trade_date"
    return conn.execute(sql, params).fetchall()


@_locked
def get_session_candles(
    conn: sqlite3.Connection, symbol: str, interval: str, session_date: date
) -> pd.DataFrame:
    """All candles for one trading date, ascending. Used by the grader to
    replay a finished session bar by bar."""
    start = int(datetime.combine(session_date, time(0, 0)).timestamp())
    end = int(datetime.combine(session_date, time(23, 59, 59)).timestamp())
    rows = conn.execute(
        """
        SELECT ts, open, high, low, close, volume FROM candles
        WHERE symbol = ? AND interval = ? AND ts BETWEEN ? AND ?
        ORDER BY ts
        """,
        (symbol, interval, start, end),
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


@_locked
def get_journal_entries_with_regime(conn: sqlite3.Connection, limit: int = 500) -> list[sqlite3.Row]:
    """Journal entries joined to the regime the engine recorded for that
    trading day.

    A LEFT JOIN, not an inner one: `daily_features` only starts from the day
    the prediction engine was first switched on, so every journal entry older
    than that has no regime attached. Those rows still belong in the record --
    dropping them would quietly shrink the trade count on the Analytics page
    and make a partial history look like a complete one.
    """
    return conn.execute(
        """
        SELECT j.*, d.structure_regime, d.day_type, d.premium_pricing
        FROM journal_entries j
        LEFT JOIN daily_features d ON d.trade_date = j.trade_date
        ORDER BY j.trade_date DESC, j.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

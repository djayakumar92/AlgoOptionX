"""Runs the HLC trade rule across a range of past trading days, reusing the
existing single-day backfill mechanism (hlc_worker.backfill_journal) for
each day not already graded, then aggregates the results.

Genuinely slow: each new day needs 15+ paced DhanHQ calls (see
hlc_worker.py's INTER_CALL_DELAY_SEC), so a multi-week backtest can take
several minutes -- this always runs in a background thread, never inline on
an HTTP request. Reuses the SAME RefreshCoordinator as the regular HLC cycle
and single-day backfill (app.state.hlc_coordinator) so a backtest can never
overlap either and double up on DhanHQ's rate limit. Per the finalized "no
Celery" stack decision (docs/product/ai-migration-requirements.md §2): an
in-memory BacktestState for live progress plus the backtest_runs table for
persisted history is this project's job-status mechanism, not a message queue.

Days already graded (has_journal_entries_for_trade_date) are skipped without
any DhanHQ calls -- re-running a backtest over a range that overlaps a
previous run only pays for the new days.
"""

from __future__ import annotations

from algooptionx.research.diagnostics import message, details

import logging
from datetime import date, datetime, timedelta

from dhanhq import dhanhq

from algooptionx.research.api.hlc_worker import backfill_journal
from algooptionx.research.api.state import BacktestState
from algooptionx.research.config import Settings
from algooptionx.research.ingestion.option_ohlc import next_trading_day
from algooptionx.research.signals import backtest_stats
from algooptionx.research.storage import repository

logger = logging.getLogger(__name__)


def trading_days(start: date, end: date) -> list[date]:
    """Mon-Fri in [start, end], inclusive. No NSE holiday calendar exists
    anywhere in this project (see hlc_worker.py's MAX_HOLIDAY_LOOKBACK
    comment) -- a holiday in range is simply a day backfill_journal will
    fail to find data for and skip, same limitation as elsewhere."""
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _empty_stats_row(start_date: date, end_date: date, status: str, error: str | None) -> dict:
    now = int(datetime.now().timestamp())
    return {
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "status": status,
        "created_ts": now, "completed_ts": now,
        "total_days": None, "graded_trades": None, "no_trade_days": None, "not_triggered": None,
        "net_points": None, "win_rate": None, "profit_factor": None, "expectancy_points": None,
        "avg_r": None, "max_drawdown_points": None, "largest_win": None, "largest_loss": None,
        "max_consecutive_losses": None, "error": error,
    }


def run_backtest(
    state: BacktestState,
    settings: Settings,
    client: dhanhq,
    conn,
    under_symbol: str,
    under_security_id: str,
    under_segment: str,
    tracked_expiry: date,
    start_date: date,
    end_date: date,
) -> None:
    session_dates = trading_days(start_date, end_date)
    state.start(len(session_dates))

    if not session_dates:
        row = _empty_stats_row(start_date, end_date, "FAILED", "Date range contains no weekdays.")
        repository.insert_backtest_run(conn, row)
        state.fail(row["error"])
        return

    try:
        for i, session_date in enumerate(session_dates, start=1):
            state.update(i, session_date.isoformat())
            trade_date = next_trading_day(session_date)
            if repository.has_journal_entries_for_trade_date(conn, trade_date.isoformat()):
                continue  # already backfilled by a previous run -- no DhanHQ calls needed
            backfill_journal(
                settings, client, conn, under_symbol, under_security_id, under_segment,
                tracked_expiry, session_date,
            )

        trade_dates = sorted(next_trading_day(d).isoformat() for d in session_dates)
        rows = repository.get_journal_entries_in_range(conn, trade_dates[0], trade_dates[-1])
        trades = [
            backtest_stats.GradedTrade(r["trade_date"], r["outcome"], r["realized_points"], r["target_points"])
            for r in rows
        ]
        stats = backtest_stats.compute_stats(trades, total_days=len(session_dates))

        now = int(datetime.now().timestamp())
        result_row = {
            "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "status": "DONE",
            "created_ts": now, "completed_ts": now,
            "total_days": stats.total_days, "graded_trades": stats.graded_trades,
            "no_trade_days": stats.no_trade_days, "not_triggered": stats.not_triggered,
            "net_points": stats.net_points, "win_rate": stats.win_rate, "profit_factor": stats.profit_factor,
            "expectancy_points": stats.expectancy_points, "avg_r": stats.avg_r,
            "max_drawdown_points": stats.max_drawdown_points, "largest_win": stats.largest_win,
            "largest_loss": stats.largest_loss, "max_consecutive_losses": stats.max_consecutive_losses,
            "error": None,
        }
        repository.insert_backtest_run(conn, result_row)
        state.finish(result_row)
    except Exception as exc:
        logger.error(message("BACKTEST_FAILED"), extra=details("BACKTEST_FAILED"))
        row = _empty_stats_row(start_date, end_date, "FAILED", message("BACKTEST_FAILED"))
        repository.insert_backtest_run(conn, row)
        state.fail(message("BACKTEST_FAILED"))

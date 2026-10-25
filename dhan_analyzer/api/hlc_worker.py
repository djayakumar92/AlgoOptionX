"""On-demand HLC computation (the user's own trading-rule strategy).

Unlike the Live page, HLC data only changes once per trading-session close --
there's nothing to gain from polling DhanHQ for it continuously. So this isn't a
background loop: run_hlc_cycle() does exactly one pass (fetch + compute + store)
and is invoked once at app startup and again whenever the user clicks "Fetch
Latest" on the page (POST /api/hlc/refresh in app.py). RefreshCoordinator makes
sure at most one cycle runs at a time -- each one costs 15+ paced API calls, so
overlapping runs would just double up on DhanHQ's rate limit for no benefit.
This module is fully self-contained: it does not read from the Live page's
LiveState.
"""

from __future__ import annotations

import calendar
import dataclasses
import logging
import threading
import time
from datetime import date, datetime, timedelta

from dhanhq import dhanhq

from dhan_analyzer import instruments
from dhan_analyzer.api.state import HlcState
from dhan_analyzer.config import Settings
from dhan_analyzer.ingestion import chart_candles
from dhan_analyzer.ingestion.chart_candles import ChartCandlesError
from dhan_analyzer.ingestion.option_ohlc import EXCHANGE_SEGMENT as OPTION_EXCHANGE_SEGMENT
from dhan_analyzer.ingestion.option_ohlc import INSTRUMENT_TYPE as OPTION_INSTRUMENT_TYPE
from dhan_analyzer.ingestion.option_ohlc import (
    OptionOhlcError,
    fetch_session_ohlc,
    last_completed_trading_day,
    next_trading_day,
)
from dhan_analyzer.instruments import InstrumentResolutionError
from dhan_analyzer.signals import hlc_strategy, journal_grading
from dhan_analyzer.signals.hlc_strategy import HlcAnalysisError, HlcResult, RangeBand, StrikeQuote
from dhan_analyzer.storage import repository

logger = logging.getLogger(__name__)

INTER_CALL_DELAY_SEC = 1.0  # conservative -- hit DH-904 Rate_Limit at 0.3s during live testing
STRIKE_STEP = 50
INSTRUMENT_TYPE_INDEX = "INDEX"
# How many extra trading days to try stepping back if the resolved date turns out
# to have no data -- last_completed_trading_day() skips weekends but can't detect
# NSE holidays (no holiday calendar), so a holiday would otherwise look identical
# to "no data yet" and never resolve.
MAX_HOLIDAY_LOOKBACK = 3


def _candidate_strikes(nifty_close: float) -> list[float]:
    rounded = round(nifty_close / STRIKE_STEP) * STRIKE_STEP
    return [rounded - STRIKE_STEP, rounded, rounded + STRIKE_STEP]


def _fetch_nifty_close(
    conn, client: dhanhq, symbol: str, security_id: str, segment: str, intraday_interval: int, session_date: date
) -> float | None:
    """NIFTY's own closing price on session_date -- usually already sitting in the
    candles table from the Live page's continuous intraday backfill (no extra API
    call needed); falls back to a direct intraday fetch for dates outside that
    rolling window (e.g. the monthly panel's anchor date, typically weeks back).

    Deliberately NOT DhanHQ's daily-candle endpoint (historical.fetch_daily) here
    -- confirmed live, it stamps each daily candle at midnight IST of the *next*
    calendar day, which silently pulled the wrong day's close under a
    calendar-date range query. fetch_session_ohlc uses intraday-minute candles
    instead, which don't have that off-by-one (same function the option-contract
    fetches already use correctly)."""
    close = repository.get_close_on_date(conn, symbol, str(intraday_interval), session_date)
    if close is not None:
        return close

    ohlc = fetch_session_ohlc(
        client, security_id, session_date, exchange_segment=segment, instrument_type=INSTRUMENT_TYPE_INDEX
    )
    return ohlc.close if ohlc is not None else None


def _build_candidates(
    client: dhanhq, symbol: str, expiry: date, strikes: list[float], session_date: date
) -> list[StrikeQuote]:
    contracts = instruments.option_contracts_for_expiry(symbol, expiry)
    by_strike_type = {(c.strike, c.option_type): c for c in contracts}

    candidates = []
    for strike in strikes:
        ce_contract = by_strike_type.get((strike, "CE"))
        pe_contract = by_strike_type.get((strike, "PE"))

        ce_ohlc = fetch_session_ohlc(client, ce_contract.security_id, session_date) if ce_contract else None
        time.sleep(INTER_CALL_DELAY_SEC)
        pe_ohlc = fetch_session_ohlc(client, pe_contract.security_id, session_date) if pe_contract else None
        time.sleep(INTER_CALL_DELAY_SEC)

        candidates.append(StrikeQuote(strike=strike, ce=ce_ohlc, pe=pe_ohlc))
    return candidates


def _resolve_for_date(
    conn,
    client: dhanhq,
    under_symbol: str,
    under_security_id: str,
    under_segment: str,
    intraday_interval: int,
    tracked_expiry: date,
    threshold_points: float,
    session_date: date,
) -> HlcResult:
    """The daily ATM panel for one specific, already-known session_date -- no
    "which date" resolution, just the fetch+analyze. Used directly by
    backfill_journal(); _resolve_session() below wraps this with "which recent
    date" logic for the normal once-a-day cycle."""
    nifty_close = _fetch_nifty_close(
        conn, client, under_symbol, under_security_id, under_segment, intraday_interval, session_date
    )
    if nifty_close is None:
        raise HlcAnalysisError(f"No NIFTY closing price found for {session_date}.")

    strikes = _candidate_strikes(nifty_close)
    candidates = _build_candidates(client, under_symbol, tracked_expiry, strikes, session_date)
    return hlc_strategy.analyze(candidates, session_date.isoformat(), nifty_close, threshold_points)


def _resolve_session(
    conn,
    client: dhanhq,
    under_symbol: str,
    under_security_id: str,
    under_segment: str,
    intraday_interval: int,
    tracked_expiry: date,
    threshold_points: float,
) -> HlcResult:
    """Try the last completed trading day; step further back if that date has no
    data at all (an NSE holiday, most likely), up to MAX_HOLIDAY_LOOKBACK times."""
    last_error: HlcAnalysisError | None = None
    for back in range(MAX_HOLIDAY_LOOKBACK + 1):
        session_date = last_completed_trading_day(back=back)
        try:
            return _resolve_for_date(
                conn, client, under_symbol, under_security_id, under_segment,
                intraday_interval, tracked_expiry, threshold_points, session_date,
            )
        except HlcAnalysisError as exc:
            last_error = exc

    raise HlcAnalysisError(
        f"No session data found in the last {MAX_HOLIDAY_LOOKBACK + 1} trading days: {last_error}"
    )


def _weekly_anchor_date(tracked_expiry: date) -> date:
    """Wednesday right after the *previous* week's Tuesday expiry -- the first
    trading day of the current weekly options series."""
    return tracked_expiry - timedelta(days=6)  # prev Tuesday (-7 days) + 1 day (Wed)


def _last_tuesday_of_month(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, last_day)
    while d.weekday() != 1:  # Tuesday = 1
        d -= timedelta(days=1)
    return d


def _monthly_expiry(today: date) -> date:
    """Last Tuesday of today's calendar month -- NIFTY's monthly expiry (current
    NSE convention, since weekly expiry moved to Tuesday)."""
    return _last_tuesday_of_month(today.year, today.month)


def _monthly_anchor_date(today: date) -> date:
    """Wednesday right after the *previous* month's monthly expiry -- the first
    trading day of the current monthly options cycle."""
    prev_month_last_day = today.replace(day=1) - timedelta(days=1)
    prev_expiry = _last_tuesday_of_month(prev_month_last_day.year, prev_month_last_day.month)
    return prev_expiry + timedelta(days=1)


def _fetch_combined_premium(
    client: dhanhq, by_strike_type: dict, strike: float, session_date: date
) -> float | None:
    """CE close + PE close at strike on session_date, or None if either leg (or
    the contract itself) is missing -- callers treat this as "skip this panel",
    not a hard failure."""
    ce_contract = by_strike_type.get((strike, "CE"))
    pe_contract = by_strike_type.get((strike, "PE"))
    if ce_contract is None or pe_contract is None:
        return None

    ce_ohlc = fetch_session_ohlc(client, ce_contract.security_id, session_date)
    time.sleep(INTER_CALL_DELAY_SEC)
    pe_ohlc = fetch_session_ohlc(client, pe_contract.security_id, session_date)
    time.sleep(INTER_CALL_DELAY_SEC)

    if ce_ohlc is None or pe_ohlc is None:
        return None
    return ce_ohlc.close + pe_ohlc.close


def _compute_range_band(
    conn,
    client: dhanhq,
    under_symbol: str,
    under_security_id: str,
    under_segment: str,
    intraday_interval: int,
    contract_expiry: date,
    anchor_date: date,
) -> RangeBand | None:
    """Weekly or monthly range band, or None if any piece is unavailable (missing
    contract, no session data, a transient API failure) -- this is additive to the
    HLC read, never allowed to fail the whole cycle the way the core daily ATM
    panel can."""
    try:
        close = _fetch_nifty_close(
            conn, client, under_symbol, under_security_id, under_segment, intraday_interval, anchor_date
        )
        if close is None:
            logger.warning("No NIFTY close for %s -- skipping this range panel", anchor_date)
            return None

        low_strike, high_strike = hlc_strategy.range_strikes(close)

        try:
            contracts = instruments.option_contracts_for_expiry(under_symbol, contract_expiry)
        except InstrumentResolutionError as exc:
            logger.warning("No option contracts for expiry %s -- skipping this range panel: %s", contract_expiry, exc)
            return None
        by_strike_type = {(c.strike, c.option_type): c for c in contracts}

        low_premium = _fetch_combined_premium(client, by_strike_type, low_strike, anchor_date)
        high_premium = _fetch_combined_premium(client, by_strike_type, high_strike, anchor_date)
        if low_premium is None or high_premium is None:
            logger.warning("Missing CE/PE premium for %s range strikes -- skipping this panel", anchor_date)
            return None

        return hlc_strategy.range_band(close, low_strike, low_premium, high_strike, high_premium)
    except OptionOhlcError as exc:
        logger.warning("Range panel fetch failed for %s, skipping this cycle: %s", anchor_date, exc)
        return None


def _log_trade_plan(conn, plan: hlc_strategy.TradePlan, combined_signal: str) -> None:
    """Persists the plan to the journal, once per trade_date -- a manual
    "Fetch Latest" re-run that still resolves the same basis session_date
    produces the same trade_date too, so this must not duplicate rows. A
    sit-out day (no legs) still gets one NO_TRADE row, so the Journal shows
    every session it looked at rather than a silent gap on Strong Bullish /
    Indecision days."""
    if repository.has_journal_entries_for_trade_date(conn, plan.trade_date):
        return
    if not plan.legs:
        repository.insert_no_trade_entry(conn, plan.session_date, plan.trade_date, combined_signal, plan.note)
        return
    for leg in plan.legs:
        repository.insert_journal_entry(
            conn, plan.session_date, plan.trade_date, leg.option_type, leg.strike,
            leg.entry_trigger, leg.target, leg.target_points, combined_signal, plan.note,
        )


def _grade_pending_journal_entries(
    conn, client: dhanhq, under_symbol: str, tracked_expiry: date, trade_date: str
) -> None:
    """Replays trade_date's actual 5-minute candles against each journal entry
    whose plan was meant to be traded on trade_date -- only meaningful once
    trade_date's own session is confirmed complete (i.e. a later HLC cycle
    resolves session_date == trade_date). Best-effort: a leg that can't be
    graded (contract not found, no candles yet) is left PENDING rather than
    failing the whole cycle."""
    pending = repository.get_pending_journal_entries(conn, trade_date)
    if not pending:
        return

    try:
        contracts = instruments.option_contracts_for_expiry(under_symbol, tracked_expiry)
    except InstrumentResolutionError as exc:
        logger.warning("Journal grading: could not resolve contracts for %s: %s", tracked_expiry, exc)
        return
    by_strike_type = {(c.strike, c.option_type): c for c in contracts}
    trade_date_obj = date.fromisoformat(trade_date)

    for entry in pending:
        contract = by_strike_type.get((entry["strike"], entry["option_type"]))
        if contract is None:
            logger.warning(
                "Journal grading: no %s contract at strike %s for %s -- leaving PENDING",
                entry["option_type"], entry["strike"], trade_date,
            )
            continue
        try:
            candles = chart_candles.fetch_candles(
                client, contract.security_id, OPTION_EXCHANGE_SEGMENT, OPTION_INSTRUMENT_TYPE, "5"
            )
        except ChartCandlesError as exc:
            logger.warning("Journal grading: candle fetch failed for entry %s: %s", entry["id"], exc)
            continue
        time.sleep(INTER_CALL_DELAY_SEC)

        trade_day_candles = [
            c for c in candles if datetime.fromtimestamp(c["ts"]).date() == trade_date_obj
        ]
        if not trade_day_candles:
            logger.warning(
                "Journal grading: no %s candles found for %s -- leaving PENDING", trade_date, entry["id"]
            )
            continue

        grade = journal_grading.grade_leg(trade_day_candles, entry["entry_trigger"], entry["target"])
        repository.update_journal_outcome(conn, entry["id"], grade.outcome, grade.realized_points)


def backfill_journal(
    settings: Settings,
    client: dhanhq,
    conn,
    under_symbol: str,
    under_security_id: str,
    under_segment: str,
    tracked_expiry: date,
    session_date: date,
) -> None:
    """Logs and immediately grades a past, already-completed session's plan --
    for filling in journal history from before the app started tracking (e.g.
    "start the journal from last Friday"), not part of the normal once-a-day
    cycle. session_date's close builds the plan; that plan is FOR trade_date
    (the next trading session after session_date), which is also already in
    the past for a backfill, so it can be graded immediately rather than
    waiting for a future rollover. Unlike run_hlc_cycle, doesn't touch
    hlc_state (this never becomes the currently-displayed plan)."""
    threshold_points = settings.hlc.threshold_points
    intraday_interval = settings.historical.intraday_interval_min

    try:
        result = _resolve_for_date(
            conn, client, under_symbol, under_security_id, under_segment,
            intraday_interval, tracked_expiry, threshold_points, session_date,
        )
        trade_date = next_trading_day(session_date)
        trade_plan = hlc_strategy.build_trade_plan(
            result, trade_date.isoformat(),
            settings.trade_plan.target_points_per_day, settings.trade_plan.max_trades_per_day,
        )
        _log_trade_plan(conn, trade_plan, result.combined_signal)
        _grade_pending_journal_entries(conn, client, under_symbol, tracked_expiry, trade_date.isoformat())
    except (OptionOhlcError, HlcAnalysisError) as exc:
        logger.warning("Journal backfill for %s failed: %s", session_date, exc)
    except Exception:
        logger.exception("Journal backfill for %s crashed unexpectedly", session_date)


def run_hlc_cycle(
    hlc_state: HlcState,
    settings: Settings,
    client: dhanhq,
    conn,
    under_symbol: str,
    under_security_id: str,
    under_segment: str,
    tracked_expiry: date,
) -> None:
    """One fetch-and-compute pass: daily ATM panel + weekly/monthly range bands.
    Stores the result (or an error) into hlc_state. Called once at startup and
    again on each manual "Fetch Latest" click -- see RefreshCoordinator below."""
    threshold_points = settings.hlc.threshold_points
    intraday_interval = settings.historical.intraday_interval_min

    try:
        result = _resolve_session(
            conn, client, under_symbol, under_security_id, under_segment,
            intraday_interval, tracked_expiry, threshold_points,
        )

        weekly = _compute_range_band(
            conn, client, under_symbol, under_security_id, under_segment,
            intraday_interval, tracked_expiry, _weekly_anchor_date(tracked_expiry),
        )

        today = date.today()
        monthly = _compute_range_band(
            conn, client, under_symbol, under_security_id, under_segment,
            intraday_interval, _monthly_expiry(today), _monthly_anchor_date(today),
        )

        session_date_obj = date.fromisoformat(result.session_date)
        trade_date = next_trading_day(session_date_obj)
        trade_plan = hlc_strategy.build_trade_plan(
            result, trade_date.isoformat(),
            settings.trade_plan.target_points_per_day, settings.trade_plan.max_trades_per_day,
        )
        result = dataclasses.replace(result, weekly=weekly, monthly=monthly, trade_plan=trade_plan)
        hlc_state.set_result(result)

        # result.session_date is a session that's now confirmed complete -- if
        # an earlier cycle logged a plan whose trade_date is exactly this date
        # (i.e. today's close is the session that plan was waiting to be acted
        # on), it can now be graded against today's real candles. Keyed off the
        # DB, not in-memory state, so this is correct even across app restarts;
        # harmless (finds nothing) on a same-day re-fetch since grading only
        # touches still-PENDING entries.
        _grade_pending_journal_entries(conn, client, under_symbol, tracked_expiry, result.session_date)
        _log_trade_plan(conn, trade_plan, result.combined_signal)
    except (OptionOhlcError, HlcAnalysisError) as exc:
        logger.warning("HLC cycle failed: %s", exc)
        hlc_state.set_error(str(exc), int(time.time()))
    except Exception:
        # A daemon thread that dies from an uncaught exception fails silently --
        # the page would show "waiting for the first cycle" forever with no
        # indication anything went wrong. Log the full traceback and surface a
        # message instead of letting the thread die here.
        logger.exception("HLC cycle crashed unexpectedly")
        hlc_state.set_error("Unexpected error -- check logs/dhan_analyzer.log", int(time.time()))


class RefreshCoordinator:
    """Ensures at most one HLC cycle runs at a time. Each cycle makes 15+ paced
    DhanHQ calls (~15-60s); a second overlapping run would just contend for the
    same rate limit for no benefit, and confuse "which result is this" ordering."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def start(self, fn, *args) -> bool:
        """Returns True if a new cycle was started, False if one was already
        running (fn was not called)."""
        if not self._lock.acquire(blocking=False):
            return False

        def _run() -> None:
            try:
                fn(*args)
            finally:
                self._lock.release()

        threading.Thread(target=_run, daemon=True).start()
        return True

    @property
    def in_progress(self) -> bool:
        acquired = self._lock.acquire(blocking=False)
        if acquired:
            self._lock.release()
            return False
        return True

"""Per-contract session High/Low/Close for the HLC page.

The option-chain endpoint (ingestion/option_chain.py) only returns LTP and greeks,
no day High/Low -- getting those for one option contract needs a separate call to
the intraday-candle endpoint. This is ephemeral, per-strike data (not persisted
like the underlying's candles table), recomputed fresh each HLC worker cycle.

fetch_session_ohlc() also gets reused for the NIFTY index itself (not just option
contracts) in hlc_worker._fetch_nifty_close, deliberately in preference to
DhanHQ's daily-candle endpoint (historical.fetch_daily): that endpoint stamps each
daily candle at midnight IST of the *next* calendar day, not the trading day it
covers -- confirmed live, this silently pulled the wrong day's close when queried
by calendar date. Intraday-minute candles don't have that off-by-one, since each
bar's own timestamp falls naturally within the session it's from.

The HLC page mirrors the user's spreadsheet, which is a once-a-day read using that
session's *completed* High/Close/Low -- not a live range that keeps expanding
through the day. So the worker always resolves to the last completed trading day
(last_completed_trading_day()), not "today so far": an in-progress day's high/low
would just be a partial, misleadingly narrow range compared to the full session.
"""

from __future__ import annotations

from algooptionx.research.diagnostics import message, provider_boundary

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from algooptionx.research.ingestion.providers import MarketDataProvider

from algooptionx.research.ingestion.historical import rows_from_response

# Confirmed from dhanhq.dhanhq.NSE_FNO / the scrip master (SEM_INSTRUMENT_NAME=OPTIDX):
# NIFTY option contracts trade on NSE_FNO, instrument type OPTIDX.
EXCHANGE_SEGMENT = "NSE_FNO"
INSTRUMENT_TYPE = "OPTIDX"
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
SATURDAY, SUNDAY = 5, 6


class OptionOhlcError(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionOhlc:
    high: float
    close: float
    low: float


def last_completed_trading_day(as_of: datetime | None = None, back: int = 0) -> date:
    """The most recent date whose session should be fully closed by now.

    `back` steps further back (skipping weekends) -- used to retry past an NSE
    holiday, which this can't otherwise detect (no holiday calendar): if a
    resolved date turns out to have no trades either, the caller retries with
    back=1, back=2, etc.
    """
    now = as_of or datetime.now()
    candidate = now.date() if now.time() >= MARKET_CLOSE else now.date() - timedelta(days=1)
    candidate -= timedelta(days=back)
    while candidate.weekday() in (SATURDAY, SUNDAY):
        candidate -= timedelta(days=1)
    return candidate


def next_trading_day(d: date) -> date:
    """The next trading session after d -- e.g. a plan built from Friday's
    close is meant to be traded on this date (the following Monday), not on
    Friday itself. Same weekend-skipping (not holiday-aware) as
    last_completed_trading_day() -- if that day turns out to be a holiday, it
    simply won't have candle data yet when grading looks for it."""
    candidate = d + timedelta(days=1)
    while candidate.weekday() in (SATURDAY, SUNDAY):
        candidate += timedelta(days=1)
    return candidate


@provider_boundary(OptionOhlcError, "CANDLE_FETCH_FAILED")
def fetch_session_ohlc(
    client: MarketDataProvider,
    security_id: str,
    session_date: date,
    interval_min: int = 5,
    exchange_segment: str = EXCHANGE_SEGMENT,
    instrument_type: str = INSTRUMENT_TYPE,
) -> SessionOhlc | None:
    """High/Low/Close for one instrument's full session on session_date.

    Defaults to option-contract segment/type (this module's usual caller);
    pass exchange_segment/instrument_type to reuse for other instruments (e.g.
    the NIFTY index itself -- see hlc_worker._fetch_nifty_close).

    None if no candles are available (e.g. session_date turned out to be a
    holiday, or the instrument was illiquid that day).
    """
    from_dt = datetime.combine(session_date, MARKET_OPEN)
    to_dt = datetime.combine(session_date, MARKET_CLOSE)

    resp = client.intraday_minute_data(
        security_id=security_id,
        exchange_segment=exchange_segment,
        instrument_type=instrument_type,
        from_date=from_dt.strftime("%Y-%m-%d %H:%M:%S"),
        to_date=to_dt.strftime("%Y-%m-%d %H:%M:%S"),
        interval=interval_min,
    )
    if resp.get("status") == "failure":
        raise OptionOhlcError(message("CANDLE_FETCH_FAILED"))

    rows = rows_from_response(resp, interval_min=interval_min)
    if not rows:
        return None

    return SessionOhlc(
        high=max(r["high"] for r in rows),
        close=rows[-1]["close"],
        low=min(r["low"] for r in rows),
    )

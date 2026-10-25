"""Candle series for the Trading Setup page's charts (Spot / ATM Call / ATM Put).

Unlike option_ohlc.py (a single session's High/Low/Close aggregated from
intraday candles) this returns the full candle series for charting -- a person
switching timeframes on a chart is nowhere near frequent enough to need
caching, so this fetches fresh every call, same "ephemeral, no persistence"
choice as option_ohlc.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from dhanhq import dhanhq

from dhan_analyzer.ingestion.historical import rows_from_response

# DhanHQ's intraday endpoint only supports 1/5/15/25/60-minute intervals -- no 3m.
INTRADAY_INTERVALS = {"1", "5", "15"}
DAILY_INTERVAL = "day"
# "1" is intentionally wider than a bare "yesterday + today" -- checked before
# today's market open with a weekend just behind it, 2 calendar days back would
# miss Friday's session entirely. Confirmed live: an 08:00 Monday check with
# lookback=2 returned zero candles for exactly this reason.
INTERVAL_LOOKBACK_DAYS = {"1": 4, "5": 5, "15": 10, DAILY_INTERVAL: 180}


class ChartCandlesError(RuntimeError):
    pass


def fetch_candles(
    client: dhanhq, security_id: str, exchange_segment: str, instrument_type: str, interval: str
) -> list[dict]:
    """interval: '1' | '5' | '15' (intraday minutes) or 'day'."""
    if interval not in INTERVAL_LOOKBACK_DAYS:
        raise ValueError(f"Unsupported interval {interval!r}; expected one of {sorted(INTERVAL_LOOKBACK_DAYS)}")

    lookback_days = INTERVAL_LOOKBACK_DAYS[interval]
    to_dt = datetime.now()
    from_dt = to_dt - timedelta(days=lookback_days)

    if interval == DAILY_INTERVAL:
        resp = client.historical_daily_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            from_date=from_dt.date().isoformat(),
            to_date=to_dt.date().isoformat(),
        )
    else:
        resp = client.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            from_date=from_dt.strftime("%Y-%m-%d %H:%M:%S"),
            to_date=to_dt.strftime("%Y-%m-%d %H:%M:%S"),
            interval=int(interval),
        )

    if resp.get("status") == "failure":
        raise ChartCandlesError(f"candle fetch failed for {security_id} ({interval}): {resp}")

    return rows_from_response(resp)

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta

from dhanhq import dhanhq

from dhan_analyzer.storage import repository

logger = logging.getLogger(__name__)

MAX_INTRADAY_WINDOW_DAYS = 90
INTER_CHUNK_DELAY_SEC = 0.3  # keeps us well under the ~5 req/sec Data API cap


class HistoricalDataError(RuntimeError):
    pass


def rows_from_response(resp: dict) -> list[dict]:
    data = resp.get("data", resp)
    timestamps = data.get("timestamp", [])
    opens = data.get("open", [])
    highs = data.get("high", [])
    lows = data.get("low", [])
    closes = data.get("close", [])
    volumes = data.get("volume", [])
    ois = data.get("open_interest", [None] * len(timestamps))

    return [
        {
            "ts": int(ts),
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "close": float(c),
            "volume": int(v) if v is not None else 0,
            "oi": int(oi) if oi is not None else None,
        }
        for ts, o, h, l, c, v, oi in zip(timestamps, opens, highs, lows, closes, volumes, ois)
    ]


def fetch_daily(
    conn,
    client: dhanhq,
    symbol: str,
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    from_date: date,
    to_date: date,
) -> int:
    """Fetch and upsert daily candles. No windowing constraint on this endpoint."""
    resp = client.historical_daily_data(
        security_id=security_id,
        exchange_segment=exchange_segment,
        instrument_type=instrument_type,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
    )
    if resp.get("status") == "failure":
        raise HistoricalDataError(f"historical_daily_data failed: {resp}")

    rows = rows_from_response(resp)
    repository.upsert_candles(conn, symbol, "day", rows)
    logger.info("Upserted %d daily candles for %s", len(rows), symbol)
    return len(rows)


def backfill_intraday(
    conn,
    client: dhanhq,
    symbol: str,
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    interval_min: int,
    from_dt: datetime,
    to_dt: datetime,
) -> int:
    """Chunk [from_dt, to_dt] into <=90-day windows and upsert intraday candles.

    Safe to call repeatedly (e.g. on every startup) since upsert_candles is idempotent.
    """
    total = 0
    chunk_start = from_dt
    while chunk_start < to_dt:
        chunk_end = min(chunk_start + timedelta(days=MAX_INTRADAY_WINDOW_DAYS), to_dt)

        resp = client.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            from_date=chunk_start.strftime("%Y-%m-%d %H:%M:%S"),
            to_date=chunk_end.strftime("%Y-%m-%d %H:%M:%S"),
            interval=interval_min,
        )
        if resp.get("status") == "failure":
            raise HistoricalDataError(
                f"intraday_minute_data failed for {chunk_start}..{chunk_end}: {resp}"
            )

        rows = rows_from_response(resp)
        repository.upsert_candles(conn, symbol, str(interval_min), rows)
        total += len(rows)

        chunk_start = chunk_end
        time.sleep(INTER_CHUNK_DELAY_SEC)

    logger.info("Backfilled %d intraday(%dm) candles for %s", total, interval_min, symbol)
    return total


def catch_up_intraday(
    conn,
    client: dhanhq,
    symbol: str,
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    interval_min: int,
    lookback_days: int,
) -> int:
    """Backfill from the latest stored candle (or lookback_days ago if none) to now."""
    last_ts = repository.last_candle_ts(conn, symbol, str(interval_min))
    from_dt = (
        datetime.fromtimestamp(last_ts) + timedelta(minutes=interval_min)
        if last_ts is not None
        else datetime.now() - timedelta(days=lookback_days)
    )
    to_dt = datetime.now()
    if from_dt >= to_dt:
        return 0
    return backfill_intraday(
        conn, client, symbol, security_id, exchange_segment, instrument_type,
        interval_min, from_dt, to_dt,
    )

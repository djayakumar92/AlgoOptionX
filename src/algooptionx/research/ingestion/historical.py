from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta

from algooptionx.research.ingestion.quality import parse_candle_response
from algooptionx.research.ingestion.providers import MarketDataProvider
from algooptionx.research.storage import repository

logger = logging.getLogger(__name__)

MAX_INTRADAY_WINDOW_DAYS = 90
INTER_CHUNK_DELAY_SEC = 0.3  # keeps us well under the ~5 req/sec Data API cap


class HistoricalDataError(RuntimeError):
    pass


def rows_from_response(resp: dict, interval_min: int | None = None) -> list[dict]:
    """Return only validated, completed rows from a Dhan candle response."""
    return parse_candle_response(resp, interval_min=interval_min).rows


def fetch_daily(
    conn,
    client: MarketDataProvider,
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
    try:
        batch = parse_candle_response(resp, interval_min=None)
    except ValueError as exc:
        raise HistoricalDataError(f"Rejected invalid daily candle data for {symbol}: {exc}") from exc
    manifest = batch.manifest(symbol, "day", from_date.isoformat(), to_date.isoformat())
    repository.upsert_candle_batch(conn, symbol, "day", batch.rows, manifest)
    logger.info("Persisted %d validated daily candles for %s", len(batch.rows), symbol)
    return len(batch.rows)


def backfill_intraday(
    conn,
    client: MarketDataProvider,
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
        try:
            batch = parse_candle_response(resp, interval_min=interval_min)
        except ValueError as exc:
            raise HistoricalDataError(
                f"Rejected invalid intraday candle data for {chunk_start}..{chunk_end}: {exc}"
            ) from exc
        requested_from = chunk_start.strftime("%Y-%m-%d %H:%M:%S")
        requested_to = chunk_end.strftime("%Y-%m-%d %H:%M:%S")
        manifest = batch.manifest(symbol, str(interval_min), requested_from, requested_to)
        repository.upsert_candle_batch(conn, symbol, str(interval_min), batch.rows, manifest)
        total += len(batch.rows)

        chunk_start = chunk_end
        time.sleep(INTER_CHUNK_DELAY_SEC)

    logger.info("Backfilled %d intraday(%dm) candles for %s", total, interval_min, symbol)
    return total


def catch_up_intraday(
    conn,
    client: MarketDataProvider,
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

"""Session-anchored aggregation using only complete, contiguous, available minutes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
from typing import Iterable, Literal

from algooptionx.market.contracts import (
    Candle,
    CandleError,
    Session,
    utc,
    validate_batch,
)


@dataclass(frozen=True)
class IncompleteWindow:
    open_at: datetime
    close_at: datetime
    missing_minutes: tuple[datetime, ...]


@dataclass(frozen=True)
class AggregationResult:
    status: Literal["READY", "INSUFFICIENT_DATA"]
    bars: tuple[Candle, ...]
    incomplete: tuple[IncompleteWindow, ...]


def _hash(children: list[Candle]) -> str:
    records = [asdict(c) for c in children]
    payload = json.dumps(
        records, sort_keys=True, separators=(",", ":"), default=lambda d: d.isoformat()
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def aggregate_completed(
    candles: Iterable[Candle], session: Session, *, as_of: datetime, minutes: int
) -> AggregationResult:
    """Future/unreceived records are invisible, even in a full replay input.

    READY requires every expected fully closed window of the requested session
    prefix. Older complete bars remain in `bars` when another window is missing,
    but callers must respect INSUFFICIENT_DATA rather than reuse an old confirmation.
    Partial trailing windows, including a short session tail, never become candles.
    """
    if type(minutes) is not int or minutes not in (5, 30):
        raise CandleError("Aggregation supports 5 or 30 minutes.")
    as_of = utc(as_of)
    available = []
    for candle in candles:
        if not isinstance(candle, Candle):
            raise CandleError("Batch entries must be validated Candle records.")
        if candle.available_at <= as_of:
            available.append(candle)
    batch = validate_batch(available, session, as_of=as_of)
    if any(c.interval_minutes != 1 for c in batch):
        raise CandleError("Aggregation requires one-minute source candles.")
    by_open = {c.open_at: c for c in batch}
    end = min(as_of, session.close_at)
    window = timedelta(minutes=minutes)
    start = session.open_at
    bars, incomplete = [], []
    while start + window <= end:
        expected = [start + timedelta(minutes=i) for i in range(minutes)]
        missing = tuple(t for t in expected if t not in by_open)
        if missing:
            incomplete.append(IncompleteWindow(start, start + window, missing))
        else:
            children = [by_open[t] for t in expected]
            first = children[0]
            bars.append(
                Candle(
                    instrument_id=first.instrument_id,
                    source_id=first.source_id,
                    data_version=first.data_version,
                    calendar_version=first.calendar_version,
                    session_id=first.session_id,
                    source_hash=_hash(children),
                    open_at=start,
                    close_at=start + window,
                    available_at=max(c.available_at for c in children),
                    open_paise=first.open_paise,
                    high_paise=max(c.high_paise for c in children),
                    low_paise=min(c.low_paise for c in children),
                    close_paise=children[-1].close_paise,
                    volume=sum(c.volume for c in children),
                    interval_minutes=minutes,
                )
            )
        start += window
    return AggregationResult(
        "READY" if bars and not incomplete else "INSUFFICIENT_DATA",
        tuple(bars),
        tuple(incomplete),
    )

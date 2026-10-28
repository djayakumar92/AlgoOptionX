"""Strict, immutable OHLCV and session boundaries for point-in-time research.

Prices are integer paise; volume is incremental units, never a cumulative counter.
These contracts do not create traded candles from simulator spot observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable


class CandleError(ValueError):
    pass


def utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise CandleError("Timestamps must be timezone-aware datetimes.")
    return value.astimezone(timezone.utc)


def _text(name: str, value: str):
    if not isinstance(value, str) or not value.strip():
        raise CandleError(f"{name} must be a nonempty string.")


@dataclass(frozen=True)
class Session:
    session_id: str
    calendar_version: str
    open_at: datetime
    close_at: datetime

    def __post_init__(self):
        _text("session_id", self.session_id)
        _text("calendar_version", self.calendar_version)
        object.__setattr__(self, "open_at", utc(self.open_at))
        object.__setattr__(self, "close_at", utc(self.close_at))
        if not timedelta(0) < self.close_at - self.open_at <= timedelta(days=1) or (
            self.close_at - self.open_at
        ) % timedelta(minutes=1):
            raise CandleError("Session must contain 1–1440 whole minutes.")


@dataclass(frozen=True)
class Candle:
    instrument_id: str
    source_id: str
    data_version: str
    calendar_version: str
    session_id: str
    source_hash: str
    open_at: datetime
    close_at: datetime
    available_at: datetime
    open_paise: int
    high_paise: int
    low_paise: int
    close_paise: int
    volume: int
    interval_minutes: int = 1
    volume_kind: str = "INCREMENTAL"

    def __post_init__(self):
        for name in (
            "instrument_id",
            "source_id",
            "data_version",
            "calendar_version",
            "session_id",
        ):
            _text(name, getattr(self, name))
        if not isinstance(self.source_hash, str) or not re.fullmatch(
            r"[a-f0-9]{64}", self.source_hash
        ):
            raise CandleError("source_hash must be a lowercase SHA-256 digest.")
        for name in ("open_at", "close_at", "available_at"):
            object.__setattr__(self, name, utc(getattr(self, name)))
        if (
            type(self.interval_minutes) is not int
            or not 1 <= self.interval_minutes <= 1440
        ):
            raise CandleError("interval_minutes must be an integer from 1 to 1440.")
        if self.close_at - self.open_at != timedelta(minutes=self.interval_minutes):
            raise CandleError("Candle duration must equal its interval.")
        if self.available_at < self.close_at:
            raise CandleError("A candle cannot be available before its close.")
        for name in ("open_paise", "high_paise", "low_paise", "close_paise"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise CandleError("OHLC must be positive integer paise.")
        if (
            not self.low_paise
            <= min(self.open_paise, self.close_paise)
            <= max(self.open_paise, self.close_paise)
            <= self.high_paise
        ):
            raise CandleError("OHLC bounds are inconsistent.")
        if (
            type(self.volume) is not int
            or self.volume < 0
            or self.volume_kind != "INCREMENTAL"
        ):
            raise CandleError("Volume must be nonnegative integer incremental units.")


def validate_batch(
    candles: Iterable[Candle], session: Session, *, as_of: datetime
) -> tuple[Candle, ...]:
    """Validate an already available, ordered batch; never sort or fill gaps silently."""
    if not isinstance(session, Session):
        raise CandleError("A validated Session record is required.")
    as_of = utc(as_of)
    batch = tuple(candles)
    identity = None
    previous = None
    for candle in batch:
        if not isinstance(candle, Candle):
            raise CandleError("Batch entries must be validated Candle records.")
        key = (candle.instrument_id, candle.source_id, candle.data_version)
        if identity is not None and key != identity:
            raise CandleError("Batch mixes instrument, source or data versions.")
        identity = key
        if (
            candle.session_id != session.session_id
            or candle.calendar_version != session.calendar_version
        ):
            raise CandleError("Batch does not match the session/calendar version.")
        if candle.open_at < session.open_at or candle.close_at > session.close_at:
            raise CandleError("Candle falls outside the session.")
        if (candle.open_at - session.open_at) % timedelta(minutes=1):
            raise CandleError(
                "Source candle is not aligned to the session minute grid."
            )
        if candle.available_at > as_of:
            raise CandleError("Candle is not yet available at as_of.")
        if previous is not None and candle.open_at < previous.close_at:
            raise CandleError(
                "Batch has duplicate, overlapping or out-of-order candles."
            )
        previous = candle
    return batch

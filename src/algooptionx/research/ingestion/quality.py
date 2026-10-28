"""Fail-closed market-data validation and provenance contracts."""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time as clock_time
from typing import Any
from zoneinfo import ZoneInfo


EXCHANGE_TZ = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = clock_time(9, 15)
MARKET_CLOSE = clock_time(15, 30)
MAX_FUTURE_SKEW_SEC = 60
VALIDATION_VERSION = 1


class DataQualityError(ValueError):
    """Raised when a provider response cannot safely be used for analysis."""


@dataclass(frozen=True)
class ValidatedCandleBatch:
    rows: list[dict[str, Any]]
    source_id: str
    received_ts: int
    source_row_count: int
    excluded_incomplete_count: int
    source_first_ts: int | None
    source_last_ts: int | None
    content_sha256: str

    def manifest(
        self,
        symbol: str,
        interval: str,
        requested_from: str,
        requested_to: str,
    ) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "symbol": symbol,
            "interval": interval,
            "requested_from": requested_from,
            "requested_to": requested_to,
            "received_ts": self.received_ts,
            "source_row_count": self.source_row_count,
            "accepted_row_count": len(self.rows),
            "excluded_incomplete_count": self.excluded_incomplete_count,
            "source_first_ts": self.source_first_ts,
            "source_last_ts": self.source_last_ts,
            "content_sha256": self.content_sha256,
            "validation_version": VALIDATION_VERSION,
            "quality_status": "VALID",
        }


def _as_array(value: object, field: str) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)):
        raise DataQualityError(f"Provider field {field!r} must be an array.")
    return value


def _number(value: object, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise DataQualityError(f"Provider field {field!r} is not numeric.")
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataQualityError(f"Provider field {field!r} is not numeric.") from exc
    if not math.isfinite(parsed) or (positive and parsed <= 0):
        raise DataQualityError(f"Provider field {field!r} is outside its valid range.")
    return parsed


def _integer(value: object, field: str, *, nonnegative: bool = False) -> int:
    if isinstance(value, bool):
        raise DataQualityError(f"Provider field {field!r} is not an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataQualityError(f"Provider field {field!r} is not an integer.") from exc
    try:
        exact = float(value) == parsed
    except (TypeError, ValueError, OverflowError):
        exact = str(value).strip() == str(parsed)
    if not exact or (nonnegative and parsed < 0):
        raise DataQualityError(f"Provider field {field!r} is outside its valid range.")
    return parsed


def _payload(resp: object) -> Mapping[str, Any]:
    if not isinstance(resp, Mapping):
        raise DataQualityError("Provider response must be an object.")
    current: Mapping[str, Any] = resp
    for _ in range(4):
        if str(current.get("status", "")).lower() == "failure":
            raise DataQualityError("Provider reported a failed market-data request.")
        if "timestamp" in current:
            return current
        child = current.get("data")
        if not isinstance(child, Mapping):
            return current
        current = child
    return current


def parse_candle_response(
    resp: object,
    *,
    source_id: str = "dhanhq",
    interval_min: int | None = None,
    now_ts: int | None = None,
) -> ValidatedCandleBatch:
    """Parse aligned OHLCV arrays, reject corrupt bars, and omit unfinished bars.

    Intraday candles are checked against the regular NSE session and interval
    boundaries. Daily candles intentionally skip that check because Dhan's
    daily endpoint timestamps have different semantics.
    """
    if not source_id.strip():
        raise DataQualityError("source_id must be non-empty.")
    if interval_min is not None and (
        isinstance(interval_min, bool) or not isinstance(interval_min, int) or interval_min <= 0
    ):
        raise DataQualityError("interval_min must be a positive integer or None.")

    data = _payload(resp)
    now = int(time.time()) if now_ts is None else int(now_ts)
    required_fields = ("timestamp", "open", "high", "low", "close", "volume")
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise DataQualityError(
            "Provider response is missing required candle fields: " + ", ".join(missing_fields)
        )
    ts_values = _as_array(data["timestamp"], "timestamp")
    fields = {
        "open": _as_array(data["open"], "open"),
        "high": _as_array(data["high"], "high"),
        "low": _as_array(data["low"], "low"),
        "close": _as_array(data["close"], "close"),
        "volume": _as_array(data["volume"], "volume"),
    }
    oi_values = _as_array(data.get("open_interest", [None] * len(ts_values)), "open_interest")
    arrays = {"timestamp": ts_values, **fields, "open_interest": oi_values}
    lengths = {name: len(values) for name, values in arrays.items()}
    if len(set(lengths.values())) > 1:
        detail = ", ".join(f"{name}={length}" for name, length in lengths.items())
        raise DataQualityError(f"Provider OHLCV arrays have inconsistent lengths ({detail}).")

    parsed_rows: list[dict[str, Any]] = []
    accepted_rows: list[dict[str, Any]] = []
    excluded_incomplete = 0
    previous_ts: int | None = None
    interval_seconds = interval_min * 60 if interval_min is not None else None

    for index in range(len(ts_values)):
        ts = _integer(ts_values[index], "timestamp", nonnegative=True)
        if ts <= 0:
            raise DataQualityError("Provider timestamp must be positive.")
        if previous_ts is not None and ts <= previous_ts:
            reason = "duplicate" if ts == previous_ts else "out of order"
            raise DataQualityError(f"Provider candle timestamps are {reason}.")
        if ts > now + MAX_FUTURE_SKEW_SEC:
            raise DataQualityError("Provider returned a future-dated candle.")

        row = {
            "ts": ts,
            "open": _number(fields["open"][index], "open", positive=True),
            "high": _number(fields["high"][index], "high", positive=True),
            "low": _number(fields["low"][index], "low", positive=True),
            "close": _number(fields["close"][index], "close", positive=True),
            "volume": _integer(fields["volume"][index], "volume", nonnegative=True),
            "oi": (
                _integer(oi_values[index], "open_interest", nonnegative=True)
                if oi_values[index] is not None
                else None
            ),
        }
        if row["high"] + 1e-9 < max(row["open"], row["close"], row["low"]):
            raise DataQualityError("Candle high is below an OHLC value.")
        if row["low"] - 1e-9 > min(row["open"], row["close"], row["high"]):
            raise DataQualityError("Candle low is above an OHLC value.")

        is_incomplete = False
        if interval_seconds is not None:
            local = datetime.fromtimestamp(ts, EXCHANGE_TZ)
            if local.weekday() >= 5 or not (MARKET_OPEN <= local.time().replace(tzinfo=None) < MARKET_CLOSE):
                raise DataQualityError("Intraday candle falls outside the regular NSE session.")
            session_minute = local.hour * 60 + local.minute
            if (session_minute - (9 * 60 + 15)) % interval_min != 0:
                raise DataQualityError("Intraday candle is not aligned to its interval.")
            if ts + interval_seconds > now:
                is_incomplete = True
                excluded_incomplete += 1
        parsed_rows.append(row)
        if not is_incomplete:
            accepted_rows.append(row)
        previous_ts = ts

    canonical = json.dumps(parsed_rows, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ValidatedCandleBatch(
        rows=accepted_rows,
        source_id=source_id,
        received_ts=now,
        source_row_count=len(parsed_rows),
        excluded_incomplete_count=excluded_incomplete,
        source_first_ts=parsed_rows[0]["ts"] if parsed_rows else None,
        source_last_ts=parsed_rows[-1]["ts"] if parsed_rows else None,
        content_sha256=digest,
    )


def is_regular_session(now_ts: int | None = None) -> bool:
    now = int(time.time()) if now_ts is None else int(now_ts)
    local = datetime.fromtimestamp(now, EXCHANGE_TZ)
    return local.weekday() < 5 and MARKET_OPEN <= local.time().replace(tzinfo=None) < MARKET_CLOSE


def require_fresh_latest_bar(
    rows: Sequence[Mapping[str, Any]],
    interval_min: int,
    *,
    now_ts: int | None = None,
    grace_sec: int = 120,
) -> None:
    """Reject an empty or stale candle series while the market is in session."""
    if not rows:
        raise DataQualityError("No validated intraday candles are available.")
    if interval_min <= 0 or grace_sec < 0:
        raise ValueError("interval_min must be positive and grace_sec non-negative.")
    now = int(time.time()) if now_ts is None else int(now_ts)
    ts = _integer(rows[-1].get("ts"), "latest candle timestamp", nonnegative=True)
    age = now - (ts + interval_min * 60)
    if age < -MAX_FUTURE_SKEW_SEC:
        raise DataQualityError("Latest candle is future-dated.")
    if age > grace_sec:
        raise DataQualityError(f"Latest completed candle is stale by {age} seconds.")


def validate_option_chain(spot_price: object, rows: Sequence[Mapping[str, Any]]) -> float:
    """Validate the minimum structure needed before a chain can reach signals."""
    spot = _number(spot_price, "spot_price", positive=True)
    if not rows:
        raise DataQualityError("Option-chain response contains no option rows.")
    seen: set[tuple[float, str]] = set()
    option_types: set[str] = set()
    numeric_fields = ("ltp", "iv", "delta", "theta", "gamma", "vega", "bid", "ask")
    count_fields = ("oi", "prev_day_oi", "volume", "bid_qty", "ask_qty")
    for row in rows:
        strike = _number(row.get("strike"), "strike", positive=True)
        option_type = row.get("option_type")
        if option_type not in ("CE", "PE"):
            raise DataQualityError("Option-chain row has an unsupported option type.")
        key = (strike, option_type)
        if key in seen:
            raise DataQualityError("Option-chain response contains duplicate strike/type rows.")
        seen.add(key)
        option_types.add(option_type)
        values: dict[str, float] = {}
        for field in numeric_fields:
            raw = row.get(field)
            if raw is None:
                continue
            minimum_positive = field == "ltp"
            value = _number(raw, field, positive=minimum_positive)
            if field in ("iv", "gamma", "vega", "bid", "ask") and value < 0:
                raise DataQualityError(f"Option-chain field {field!r} cannot be negative.")
            if field == "delta" and not -1 <= value <= 1:
                raise DataQualityError("Option-chain delta must be between -1 and 1.")
            values[field] = value
        for field in count_fields:
            raw = row.get(field)
            if raw is not None:
                _integer(raw, field, nonnegative=True)
        if values.get("bid") is not None and values.get("ask") is not None:
            if values["bid"] > 0 and values["ask"] > 0 and values["bid"] > values["ask"]:
                raise DataQualityError("Option-chain bid exceeds ask.")
    if option_types != {"CE", "PE"}:
        raise DataQualityError("Option-chain response must contain both CE and PE rows.")
    return spot

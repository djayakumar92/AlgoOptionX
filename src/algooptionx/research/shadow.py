"""Read-only point-in-time adapter over retained research analytics.

Run `python -m algooptionx.research.shadow --demo` for an explicitly synthetic
engineering report. No provider, broker, worker, database or paper engine is imported.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime, timedelta
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import AwareDatetime, Field, field_validator, model_validator

from algooptionx.intelligence.contracts import (
    Decision,
    Name,
    Observation,
    Record,
    Source,
)
from algooptionx.intelligence.decision import compose_shadow
from algooptionx.market.aggregation import aggregate_completed
from algooptionx.market.contracts import Candle, CandleError, Session, utc
from algooptionx.research.signals import (
    market_structure as ms,
    regime,
    sentiment,
    trend,
)

IST = ZoneInfo("Asia/Kolkata")
MAX_LEGACY_PAISE = 2**53 - 1
MAX_LEGACY_UNITS = 10**12


class OptionQuote(Record):
    instrument_id: Name
    strike_paise: int = Field(gt=0, le=MAX_LEGACY_PAISE)
    right: Literal["CE", "PE"]
    bid_paise: int = Field(gt=0, le=MAX_LEGACY_PAISE)
    ask_paise: int = Field(gt=0, le=MAX_LEGACY_PAISE)
    oi: int = Field(ge=0, le=MAX_LEGACY_UNITS)
    volume: int = Field(ge=0, le=MAX_LEGACY_UNITS)
    iv_percent: float | None = Field(default=None, gt=0, le=1000)

    @model_validator(mode="after")
    def quote_bounds(self):
        if self.bid_paise > self.ask_paise:
            raise ValueError("Crossed quotes are invalid.")
        return self


class ChainSnapshot(Record):
    underlying_id: Name
    source_id: Name
    data_version: Name
    calendar_version: Name
    instrument_version: Name
    event_at: AwareDatetime
    available_at: AwareDatetime
    expiry: date
    quotes: tuple[OptionQuote, ...] = Field(min_length=2, max_length=2048)

    @field_validator("event_at", "available_at")
    @classmethod
    def normalize_time(cls, value):
        return utc(value)

    @model_validator(mode="after")
    def consistent_chain(self):
        if self.event_at > self.available_at:
            raise ValueError("Quote event cannot follow availability.")
        if self.expiry < self.event_at.astimezone(IST).date():
            raise ValueError("Snapshot expiry predates its event.")
        pairs = [(q.strike_paise, q.right) for q in self.quotes]
        if len(set(pairs)) != len(pairs) or len(
            {q.instrument_id for q in self.quotes}
        ) != len(pairs):
            raise ValueError("Duplicate chain contract identities.")
        if {q.right for q in self.quotes} != {"CE", "PE"}:
            raise ValueError("Both option rights are required.")
        return self


class ShadowInput(Record):
    session: Session
    candles: tuple[Candle, ...] = Field(max_length=1440)
    as_of: AwareDatetime
    instrument_id: Name
    dataset_id: Name
    data_kind: Literal["SYNTHETIC", "HISTORICAL", "LICENSED_LIVE"]
    instrument_version: Name
    chain: ChainSnapshot | None = None


def _digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=lambda d: d.isoformat(),
        ).encode()
    ).hexdigest()


def _frame(bars: tuple[Candle, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(
                ts=int(c.open_at.timestamp()),
                open=c.open_paise / 100,
                high=c.high_paise / 100,
                low=c.low_paise / 100,
                close=c.close_paise / 100,
                volume=c.volume,
            )
            for c in bars
        ],
        columns=["ts", "open", "high", "low", "close", "volume"],
    )


def evaluate_shadow(request: ShadowInput) -> Decision:
    # Revalidate even preconstructed instances; this is not a model/execution gate.
    request = ShadowInput.model_validate(request)
    as_of = utc(request.as_of)
    eligible = tuple(c for c in request.candles if c.available_at <= as_of)
    snapshot = (
        request.chain
        if request.chain is not None and request.chain.available_at <= as_of
        else None
    )
    source_hash = _digest(
        {
            "candles": [asdict(c) for c in eligible],
            "chain": snapshot.model_dump(mode="json") if snapshot else None,
            "session": asdict(request.session),
            "instrument_id": request.instrument_id,
            "instrument_version": request.instrument_version,
        }
    )
    source = Source(
        kind=request.data_kind,
        dataset_id=request.dataset_id,
        sha256=source_hash,
        calendar_version=request.session.calendar_version,
        instrument_version=request.instrument_version,
    )
    observations = []
    inside = request.session.open_at <= as_of < request.session.close_at
    metadata_ok = all(c.instrument_id == request.instrument_id for c in eligible)

    def observe(
        skill,
        metric,
        value,
        *,
        status="OBSERVED",
        unit=None,
        timeframe=None,
        bars=(),
        event=None,
        available=None,
        reasons=(),
    ):
        observations.append(
            Observation(
                skill_id=skill,
                version="legacy-shadow-1",
                metric=metric,
                status=status,
                value=value,
                unit=unit,
                timeframe_minutes=timeframe,
                event_at=event or (bars[-1].close_at if bars else as_of),
                available_at=available
                or (max(c.available_at for c in bars) if bars else as_of),
                source_hash=_digest([asdict(c) for c in bars]) if bars else source_hash,
                reason_codes=reasons,
            )
        )

    aggregates = {}
    for minutes in (5, 30):
        try:
            if not inside or not metadata_ok:
                raise CandleError("Session or instrument is unavailable.")
            if any(
                c.volume > MAX_LEGACY_UNITS
                or max(c.open_paise, c.high_paise, c.low_paise, c.close_paise)
                > MAX_LEGACY_PAISE
                for c in eligible
            ):
                raise CandleError("Source exceeds the supported legacy numeric range.")
            result = aggregate_completed(
                eligible, request.session, as_of=as_of, minutes=minutes
            )
            bars = result.bars
            ready = result.status == "READY"
            aggregates[minutes] = bars if ready else ()
            observe(
                "M04",
                "completion",
                ready if ready else None,
                status="OBSERVED" if ready else "INSUFFICIENT_DATA",
                timeframe=minutes,
                bars=bars if ready else (),
                reasons=()
                if ready
                else (
                    ("MISSING_OR_LATE_MINUTES",)
                    if result.incomplete
                    else ("NO_COMPLETED_WINDOW",)
                ),
            )
        except CandleError:
            aggregates[minutes] = ()
            observe(
                "M04",
                "completion",
                None,
                status="INVALID_DATA",
                timeframe=minutes,
                reasons=("INVALID_SESSION_INSTRUMENT_OR_CANDLE_BATCH",),
            )
        bars = aggregates[minutes]
        if len(bars) < 7:
            observe(
                "F02",
                "structure",
                None,
                status="INSUFFICIENT_DATA",
                unit="direction",
                timeframe=minutes,
                reasons=("STRUCTURE_WARMUP_NOT_MET",),
            )
        else:
            frame = _frame(bars)
            swings = ms.find_swings(frame)
            direction, _, _ = ms.classify_structure(swings)
            # Pivot time is not availability. Conservatively attribute the summary
            # to the latest complete input/receipt, including right-hand neighbors.
            observe(
                "F02",
                "structure",
                direction,
                unit="direction",
                timeframe=minutes,
                bars=bars,
            )

    # A future snapshot is deliberately invisible; absent and future are equivalent.
    chain_ok = (
        snapshot is not None
        and inside
        and (
            snapshot.underlying_id == request.instrument_id
            and snapshot.calendar_version == request.session.calendar_version
            and snapshot.instrument_version == request.instrument_version
            and timedelta(0) <= as_of - snapshot.event_at <= timedelta(minutes=1)
            and snapshot.event_at >= request.session.open_at
            and snapshot.expiry >= as_of.astimezone(IST).date()
            and (
                not eligible
                or (
                    snapshot.source_id == eligible[0].source_id
                    and snapshot.data_version == eligible[0].data_version
                )
            )
        )
    )
    observe(
        "O05",
        "chain_quality",
        True if chain_ok else None,
        status="OBSERVED" if chain_ok else "INSUFFICIENT_DATA",
        event=snapshot.event_at if chain_ok else as_of,
        available=snapshot.available_at if chain_ok else as_of,
        reasons=()
        if chain_ok
        else (
            ("CHAIN_UNAVAILABLE",)
            if snapshot is None
            else ("CHAIN_STALE_OR_METADATA_MISMATCH",)
        ),
    )
    five = aggregates[5]
    if five and chain_ok:
        frame = _frame(five)
        swings = ms.find_swings(frame)
        direction, bos, choch = ms.classify_structure(swings)
        chop = ms.choppiness_index(frame).iloc[-1] if len(frame) >= 14 else None
        chop = float(chop) if chop is not None and pd.notna(chop) else None
        structure = ms.MarketStructureSummary(
            swings=swings,
            structure_trend=direction,
            last_bos=bos,
            last_choch=choch,
            day_type=ms.classify_day_type(frame, ib_minutes=30, bar_minutes=5),
            chop=chop,
            prev_day_high=None,
            prev_day_low=None,
            prev_week_high=None,
            prev_week_low=None,
        )
        chain = pd.DataFrame(
            [
                dict(
                    strike=q.strike_paise / 100,
                    option_type=q.right,
                    oi=q.oi,
                    volume=q.volume,
                    iv=q.iv_percent,
                    ltp=(q.bid_paise + q.ask_paise) / 200,
                )
                for q in snapshot.quotes
            ]
        )
        spot = five[-1].close_paise / 100
        trend_read = trend.summarize(frame)
        regime_read = regime.summarize(
            spot_price=spot,
            chain=chain,
            daily_candles=pd.DataFrame(
                columns=["ts", "open", "high", "low", "close", "volume"]
            ),
            intraday_candles=frame,
            structure=structure,
            gex_summary=None,
            trend=trend_read,
            tracked_expiry=snapshot.expiry,
            now=as_of.astimezone(IST),
        )
        known_regime = regime_read.structure_regime != "UNKNOWN"
        event = max(five[-1].close_at, snapshot.event_at)
        availability = max(max(c.available_at for c in five), snapshot.available_at)
        observe(
            "M01",
            "structure_regime",
            regime_read.structure_regime if known_regime else None,
            status="OBSERVED" if known_regime else "INSUFFICIENT_DATA",
            unit="regime",
            event=event,
            available=availability,
            reasons=() if known_regime else ("REGIME_NOT_ESTABLISHED",),
        )
        sentiment_read = sentiment.summarize(chain, spot)
        observe(
            "O06",
            "pcr_oi",
            sentiment_read.pcr_oi,
            status="OBSERVED"
            if sentiment_read.pcr_oi is not None
            else "INSUFFICIENT_DATA",
            unit="ratio",
            event=event,
            available=availability,
        )
        observe(
            "M01",
            "premium_stance_score",
            regime_read.stance_score,
            unit="rule-score",
            event=event,
            available=availability,
        )
    else:
        observe(
            "M01",
            "structure_regime",
            None,
            status="INSUFFICIENT_DATA",
            unit="regime",
            reasons=("REGIME_INPUTS_UNAVAILABLE",),
        )
    if inside:
        interval = timedelta(minutes=5)
        next_close = (
            request.session.open_at
            + ((as_of - request.session.open_at) // interval + 1) * interval
        )
        expiry = min(next_close, request.session.close_at, as_of + interval)
    else:
        expiry = as_of + timedelta(seconds=1)
    return compose_shadow(
        instrument_id=request.instrument_id,
        as_of=as_of,
        source=source,
        evidence=tuple(observations),
        valid_until=expiry,
    )


def demo_input() -> ShadowInput:
    """Independent synthetic OHLCV fixture, not resampled paper-engine spot marks."""
    start = datetime(2026, 11, 2, 9, 15, tzinfo=IST)
    session = Session(
        "sim-20261102", "fixture-calendar-v1", start, start + timedelta(minutes=375)
    )
    bars = []
    previous = 2_440_000
    for i in range(360):
        close = 2_440_000 + round(4000 * math.sin(i / 23) + i * 8)
        bars.append(
            Candle(
                instrument_id="SIM-NIFTY",
                source_id="fixture",
                data_version="demo-1",
                calendar_version=session.calendar_version,
                session_id=session.session_id,
                source_hash="a" * 64,
                open_at=start + timedelta(minutes=i),
                close_at=start + timedelta(minutes=i + 1),
                available_at=start + timedelta(minutes=i + 1, seconds=1),
                open_paise=previous,
                high_paise=max(previous, close) + 100,
                low_paise=min(previous, close) - 100,
                close_paise=close,
                volume=100 + i % 20,
            )
        )
        previous = close
    as_of = start + timedelta(minutes=360, seconds=1)
    chain = ChainSnapshot(
        underlying_id="SIM-NIFTY",
        source_id="fixture",
        data_version="demo-1",
        calendar_version=session.calendar_version,
        instrument_version="fixture-options-v1",
        event_at=as_of - timedelta(seconds=1),
        available_at=as_of,
        expiry=date(2026, 11, 3),
        quotes=tuple(
            OptionQuote(
                instrument_id=f"SIM-{strike}-{right}",
                strike_paise=strike,
                right=right,
                bid_paise=8000,
                ask_paise=8100,
                oi=40000,
                volume=1000,
                iv_percent=14.0,
            )
            for strike in (2440000, 2445000)
            for right in ("CE", "PE")
        ),
    )
    return ShadowInput(
        session=session,
        candles=tuple(bars),
        as_of=as_of,
        instrument_id="SIM-NIFTY",
        dataset_id="synthetic-shadow-demo-v1",
        data_kind="SYNTHETIC",
        instrument_version="fixture-options-v1",
        chain=chain,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true")
    group.add_argument("--input", type=Path)
    group.add_argument(
        "--schema", nargs="?", const="decision", choices=("decision", "input")
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.schema:
            text = (
                json.dumps(
                    (
                        Decision if args.schema == "decision" else ShadowInput
                    ).model_json_schema(),
                    indent=2,
                )
                + "\n"
            )
        else:
            if args.input is not None and args.input.stat().st_size > 20 * 1024 * 1024:
                raise ValueError("Input exceeds20MiB.")
            request = (
                demo_input()
                if args.demo
                else ShadowInput.model_validate_json(args.input.read_text())
            )
            text = evaluate_shadow(request).model_dump_json(indent=2) + "\n"
        if args.output:
            # Never overwrite an existing report/history or follow an existing symlink.
            with args.output.open("x") as output:
                output.write(text)
        else:
            print(text, end="")
        return 0
    except (ValueError, OSError, OverflowError) as exc:
        # Do not echo untrusted input values or credential-bearing paths/payloads.
        print(
            json.dumps({"status": "failed", "error_type": type(exc).__name__}),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

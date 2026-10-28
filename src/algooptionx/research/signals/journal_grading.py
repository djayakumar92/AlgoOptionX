"""Retrospectively grades one TradeLeg against a completed session's real
5-minute candles: did the plan's entry trigger, and if so, did it hit target or
stop first?

This never runs live/predictively -- it only replays a session's candles after
that session is fully closed (see hlc_worker.py's rollover check), so it can't
tell the user to act. It exists purely to answer "did the plan from
{session_date} actually work?" for the Journal page.

The stop is a *trailing* rule (previous completed 5-min candle's high), not a
fixed price -- see TradeLeg.stop_rule -- so it has to be recomputed candle by
candle here, not looked up from a stored number.
"""

from __future__ import annotations

from dataclasses import dataclass

NOT_TRIGGERED = "NOT_TRIGGERED"
TARGET_HIT = "TARGET_HIT"
STOP_HIT = "STOP_HIT"
OPEN_AT_CLOSE = "OPEN_AT_CLOSE"  # intraday-only rule -- entered but neither hit before session end
NO_TRADE = "NO_TRADE"  # build_trade_plan() sat out this session (Strong Bullish / Indecision) -- no leg to grade


@dataclass(frozen=True)
class GradeResult:
    outcome: str
    realized_points: float | None  # None only for NOT_TRIGGERED


def grade_leg(candles: list[dict], entry_trigger: float, target: float) -> GradeResult:
    """candles: chronological 5-minute bars for the sold leg's premium, each a
    dict with at least 'high', 'low', 'close' (matches chart_candles.py's row
    shape). A SELL only fills if price actually trades up to entry_trigger."""
    entry_idx = next((i for i, c in enumerate(candles) if c["high"] >= entry_trigger), None)
    if entry_idx is None:
        return GradeResult(NOT_TRIGGERED, None)

    for i in range(entry_idx + 1, len(candles)):
        stop_level = candles[i - 1]["high"]  # previous completed candle's high, recomputed each bar
        candle = candles[i]
        if candle["high"] >= stop_level:
            return GradeResult(STOP_HIT, entry_trigger - stop_level)
        if candle["low"] <= target:
            return GradeResult(TARGET_HIT, entry_trigger - target)

    last_close = candles[-1]["close"]
    return GradeResult(OPEN_AT_CLOSE, entry_trigger - last_close)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from dhan_analyzer.signals.momentum import MomentumSummary
from dhan_analyzer.signals.oi_behavior import OiBehaviorSummary
from dhan_analyzer.signals.sentiment import SentimentSummary
from dhan_analyzer.signals.trend import TrendSummary

BULLISH, BEARISH, NEUTRAL = "BULLISH", "BEARISH", "NEUTRAL"


@dataclass(frozen=True)
class Suggestion:
    timestamp: str
    spot_price: float
    bias: str
    confidence: float  # 0-100
    contributing_signals: dict = field(default_factory=dict)
    suggested_instrument: str | None = None
    entry_zone: str | None = None
    stop_loss: str | None = None
    watch_level: str | None = None
    rationale: str = ""


def _nearest_available_strike(strikes: list[float], target: float) -> float | None:
    if not strikes:
        return None
    return min(strikes, key=lambda s: abs(s - target))


def combine(
    spot_price: float,
    chain: pd.DataFrame,
    sentiment: SentimentSummary,
    oi_behavior: OiBehaviorSummary,
    trend: TrendSummary,
    momentum: MomentumSummary,
    expiry_label: str,
    underlying_symbol: str,
) -> Suggestion:
    """Merge the four signal groups into one human-readable Suggestion.

    This is a transparent, equally-weighted vote across signal groups -- not a
    trained/backtested model. It exists to surface a readable, auditable bias
    for Phase 1 (display only); a future backtesting phase should validate or
    replace this weighting before it informs any real trading decision.
    """
    leans = {
        "sentiment": sentiment.bias_lean,
        "oi_behavior": oi_behavior.bias_lean,
        "trend": trend.bias_lean,
        "momentum": momentum.bias_lean,
    }
    bull_votes = sum(1 for v in leans.values() if v == BULLISH)
    bear_votes = sum(1 for v in leans.values() if v == BEARISH)
    total = len(leans)

    if bull_votes > bear_votes:
        bias = BULLISH
    elif bear_votes > bull_votes:
        bias = BEARISH
    else:
        bias = NEUTRAL

    agreeing = max(bull_votes, bear_votes)
    confidence = round((agreeing / total) * 100, 1)
    if trend.trend_strength == "STRONG" and bias != NEUTRAL:
        confidence = min(100.0, confidence + 10)

    suggested_instrument = entry_zone = stop_loss = watch_level = None

    if bias != NEUTRAL and not chain.empty:
        option_type = "CE" if bias == BULLISH else "PE"
        side_strikes = sorted(chain.loc[chain["option_type"] == option_type, "strike"].unique())
        atm = _nearest_available_strike(side_strikes, spot_price)
        if atm is not None:
            suggested_instrument = f"{underlying_symbol} {atm:g} {option_type} ({expiry_label})"

        if trend.vwap is not None:
            entry_zone = f"on pullback toward VWAP ~{trend.vwap:g}"
        else:
            entry_zone = "near current market price"

        if trend.vwap is not None:
            stop_loss = (
                f"underlying below {trend.vwap:g} (VWAP)"
                if bias == BULLISH
                else f"underlying above {trend.vwap:g} (VWAP)"
            )

        watch_candidates = (
            sentiment.top_put_oi_strikes if bias == BULLISH else sentiment.top_call_oi_strikes
        )
        if watch_candidates:
            watch_level = f"{'support' if bias == BULLISH else 'resistance'} near {watch_candidates[0]:g}"
        elif sentiment.max_pain_strike is not None:
            watch_level = f"max pain at {sentiment.max_pain_strike:g}"

    agree_str = ", ".join(f"{k}={v}" for k, v in leans.items())
    rationale = f"{agreeing}/{total} signals lean {bias}: {agree_str}."
    if sentiment.pcr_oi is not None:
        rationale += f" PCR(OI)={sentiment.pcr_oi}."
    if sentiment.max_pain_strike is not None:
        rationale += f" Max pain={sentiment.max_pain_strike:g}."

    return Suggestion(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        spot_price=spot_price,
        bias=bias,
        confidence=confidence,
        contributing_signals=leans,
        suggested_instrument=suggested_instrument,
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        watch_level=watch_level,
        rationale=rationale,
    )

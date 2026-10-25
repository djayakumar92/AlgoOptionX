from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

LONG_BUILDUP = "LONG_BUILDUP"
SHORT_BUILDUP = "SHORT_BUILDUP"
SHORT_COVERING = "SHORT_COVERING"
LONG_UNWINDING = "LONG_UNWINDING"
NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class OiBehaviorSummary:
    per_contract: pd.DataFrame  # strike, option_type, ltp_change, oi_change, behavior
    call_long_buildup_count: int
    put_long_buildup_count: int
    call_short_buildup_count: int
    put_short_buildup_count: int
    bias_lean: str  # BULLISH | BEARISH | NEUTRAL


def _classify(price_change: float, oi_change: float) -> str:
    if price_change > 0 and oi_change > 0:
        return LONG_BUILDUP
    if price_change > 0 and oi_change < 0:
        return SHORT_COVERING
    if price_change < 0 and oi_change > 0:
        return SHORT_BUILDUP
    if price_change < 0 and oi_change < 0:
        return LONG_UNWINDING
    return NEUTRAL


def classify(latest: pd.DataFrame, previous: pd.DataFrame | None) -> OiBehaviorSummary:
    """Classify each strike/option_type's OI behavior between two consecutive polls.

    Per-contract classification (price of that option's premium vs its own OI) --
    the standard futures-style long/short buildup framework applied per contract.
    Aggregate bias_lean is a simple heuristic: put long-buildup vs call long-buildup
    counts (put writing/long-buildup skew = bullish lean, and vice versa for calls),
    not a rigorous model -- treat it as one input among several in combine.py.
    """
    if previous is None or previous.empty or latest.empty:
        empty = pd.DataFrame(
            columns=["strike", "option_type", "ltp_change", "oi_change", "behavior"]
        )
        return OiBehaviorSummary(empty, 0, 0, 0, 0, "NEUTRAL")

    merged = latest.merge(
        previous,
        on=["strike", "option_type"],
        suffixes=("", "_prev"),
        how="inner",
    )
    merged["ltp_change"] = merged["ltp"] - merged["ltp_prev"]
    merged["oi_change"] = merged["oi"] - merged["oi_prev"]
    merged["behavior"] = [
        _classify(pc, oc) for pc, oc in zip(merged["ltp_change"], merged["oi_change"])
    ]

    per_contract = merged[["strike", "option_type", "ltp_change", "oi_change", "behavior"]]

    call_lb = int(((per_contract["option_type"] == "CE") & (per_contract["behavior"] == LONG_BUILDUP)).sum())
    put_lb = int(((per_contract["option_type"] == "PE") & (per_contract["behavior"] == LONG_BUILDUP)).sum())
    call_sb = int(((per_contract["option_type"] == "CE") & (per_contract["behavior"] == SHORT_BUILDUP)).sum())
    put_sb = int(((per_contract["option_type"] == "PE") & (per_contract["behavior"] == SHORT_BUILDUP)).sum())

    bias_lean = "NEUTRAL"
    if put_lb > call_lb and put_lb > 0:
        bias_lean = "BULLISH"
    elif call_lb > put_lb and call_lb > 0:
        bias_lean = "BEARISH"

    return OiBehaviorSummary(per_contract, call_lb, put_lb, call_sb, put_sb, bias_lean)

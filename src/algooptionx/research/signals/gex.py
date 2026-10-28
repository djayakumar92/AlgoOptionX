"""Gamma Exposure (GEX) -- where dealer hedging flow is concentrated, and
whether that flow is currently damping moves or amplifying them.

Grounded in `.claude/skills/nifty-options-domain-knowledge/references/
oi-pcr-institutional-practice.md` §2-3 (loaded before writing this). The
research's finding, verbatim in substance: to the extent price gravitates
toward high-OI strikes, the causal mechanism is dealer/market-maker
delta-hedging flow, **not** "writers minimizing payout" -- and max pain is a
crude, static approximation of what gamma exposure measures properly and
dynamically. That reference explicitly names strike-by-strike
`gamma x OI`, calls positive / puts negative from the dealer's perspective,
as "the professionally-credible replacement". This module is that.

## The one honest caveat, stated up front

The sign convention below assumes the standard dealer-positioning model:
dealers are net **long calls / short puts** against customer flow, so call
gamma counts positive and put gamma negative. NSE publishes no dealer
inventory data, so that assumption **cannot be verified from this feed** --
it is the same assumption every public GEX tool makes, and it is an
assumption, not a measurement. Everything here is therefore presented as
"where hedging flow is likely concentrated", never as a guaranteed level.

Consistent with that, absolute rupee GEX is deliberately NOT reported. The
notional multiplier (lot size, spot^2, a 1% move convention) is a constant
that cancels out of every comparison this analyzer actually makes -- which
strike carries the most gamma, where cumulative gamma flips sign, whether
net gamma is positive or negative. Reporting a big rupee number would add
false precision on top of an unverifiable assumption; the relative
`gamma x OI` units below carry all the decision-relevant information.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

CALL, PUT = "CE", "PE"

POSITIVE_GAMMA = "POSITIVE_GAMMA"  # dealers hedge against the move -> pinning / mean-reverting
NEGATIVE_GAMMA = "NEGATIVE_GAMMA"  # dealers hedge with the move -> acceleration / trending
GAMMA_UNKNOWN = "UNKNOWN"  # no usable gamma data in the chain

# Net GEX within +/- this fraction of the largest absolute strike exposure is
# treated as "balanced" rather than decisively positive or negative -- a
# first calibration to stop a near-zero total flipping regime label on noise,
# not a sourced constant.
_BALANCED_BAND = 0.10


@dataclass(frozen=True)
class StrikeGex:
    strike: float
    call_gex: float  # gamma x OI on the CE side (positive by convention)
    put_gex: float  # gamma x OI on the PE side (negative by convention)
    net_gex: float  # call_gex + put_gex
    total_abs_gex: float  # |call| + |put| -- raw hedging weight at this strike, ignoring sign


@dataclass(frozen=True)
class GexSummary:
    """Relative units (gamma x OI), not rupees -- see module docstring."""

    per_strike: list[StrikeGex]
    net_gex: float
    regime: str  # POSITIVE_GAMMA | NEGATIVE_GAMMA | UNKNOWN
    gamma_flip_strike: float | None  # where cumulative net GEX crosses zero
    call_wall_strike: float | None  # heaviest positive-gamma strike -- likely resistance magnet
    put_wall_strike: float | None  # heaviest negative-gamma strike -- likely support magnet
    largest_gamma_strike: float | None  # heaviest total hedging weight, either side
    note: str


def _empty(note: str) -> GexSummary:
    return GexSummary([], 0.0, GAMMA_UNKNOWN, None, None, None, None, note)


def compute_strike_gex(chain: pd.DataFrame, spot_price: float, strike_range_pct: float = 0.06) -> list[StrikeGex]:
    """Per-strike gamma x OI, calls positive / puts negative, restricted to
    strikes within strike_range_pct of spot.

    The range restriction matters more here than it does for plain OI walls:
    gamma collapses toward zero away from ATM, so far strikes contribute
    almost nothing but do drag the cumulative-sum crossing around when their
    OI is large. Same 6% default as oi_walls.detect_walls() for consistency.
    """
    if chain.empty or "gamma" not in chain.columns or "oi" not in chain.columns:
        return []

    lo, hi = spot_price * (1 - strike_range_pct), spot_price * (1 + strike_range_pct)
    nearby = chain[(chain["strike"] >= lo) & (chain["strike"] <= hi)].copy()
    if nearby.empty:
        return []

    nearby["gamma"] = pd.to_numeric(nearby["gamma"], errors="coerce")
    nearby["oi"] = pd.to_numeric(nearby["oi"], errors="coerce")
    nearby = nearby.dropna(subset=["gamma", "oi"])
    if nearby.empty:
        return []

    # Dhan returns put gamma as a positive number (gamma is positive for both
    # long calls and long puts); the negative sign below is the *dealer
    # positioning* convention, applied here rather than trusting the feed's
    # sign. abs() first so a feed that ever starts signing puts negatively
    # can't silently double-negate into a positive contribution.
    rows: list[StrikeGex] = []
    for strike, group in nearby.groupby("strike"):
        ce = group[group["option_type"] == CALL]
        pe = group[group["option_type"] == PUT]
        call_gex = float((ce["gamma"].abs() * ce["oi"]).sum())
        put_gex = -float((pe["gamma"].abs() * pe["oi"]).sum())
        rows.append(
            StrikeGex(
                strike=float(strike),
                call_gex=call_gex,
                put_gex=put_gex,
                net_gex=call_gex + put_gex,
                total_abs_gex=abs(call_gex) + abs(put_gex),
            )
        )

    return sorted(rows, key=lambda r: r.strike)


def gamma_flip_strike(per_strike: list[StrikeGex]) -> float | None:
    """Strike where the running cumulative net GEX changes sign -- the
    conventional "zero gamma" / flip level.

    Above it, cumulative dealer gamma is positive (hedging damps moves);
    below it, negative (hedging amplifies them). Returns the strike where
    the crossing happens, or None if the cumulative sum never changes sign
    (i.e. the whole nearby chain sits on one side).

    Linear interpolation between the two bracketing strikes is deliberately
    NOT done: NIFTY strikes are 50 points apart, and interpolating to a
    fractional level would imply a precision this data does not support.
    """
    if len(per_strike) < 2:
        return None

    cumulative = 0.0
    previous = None
    for row in per_strike:
        cumulative += row.net_gex
        if previous is not None and (previous < 0) != (cumulative < 0):
            return row.strike
        previous = cumulative
    return None


def summarize(chain: pd.DataFrame, spot_price: float, strike_range_pct: float = 0.06) -> GexSummary:
    per_strike = compute_strike_gex(chain, spot_price, strike_range_pct)
    if not per_strike:
        return _empty(
            "No usable gamma/OI data in the nearby chain -- GEX not computed. "
            "The option-chain feed supplies greeks only during market hours."
        )

    net = sum(r.net_gex for r in per_strike)
    largest_abs = max(abs(r.net_gex) for r in per_strike) or 1.0

    if abs(net) < _BALANCED_BAND * largest_abs:
        regime = POSITIVE_GAMMA if net >= 0 else NEGATIVE_GAMMA
        note = (
            "Net gamma is close to balanced -- the pinning/acceleration read is weak here, "
            "treat it as a tiebreaker rather than a driver."
        )
    elif net > 0:
        regime = POSITIVE_GAMMA
        note = (
            "Net positive gamma: dealer hedging leans against moves (sell rallies, buy dips), "
            "which historically shows up as range-bound, pin-prone behaviour. Assumes the standard "
            "dealer-positioning convention -- see this module's docstring."
        )
    else:
        regime = NEGATIVE_GAMMA
        note = (
            "Net negative gamma: dealer hedging leans with moves, which amplifies rather than damps "
            "them -- the condition under which pinning logic (including max pain) is least reliable "
            "and trend/breakout behaviour is more likely."
        )

    calls_positive = [r for r in per_strike if r.call_gex > 0]
    puts_negative = [r for r in per_strike if r.put_gex < 0]

    return GexSummary(
        per_strike=per_strike,
        net_gex=net,
        regime=regime,
        gamma_flip_strike=gamma_flip_strike(per_strike),
        call_wall_strike=max(calls_positive, key=lambda r: r.call_gex).strike if calls_positive else None,
        put_wall_strike=min(puts_negative, key=lambda r: r.put_gex).strike if puts_negative else None,
        largest_gamma_strike=max(per_strike, key=lambda r: r.total_abs_gex).strike,
        note=note,
    )

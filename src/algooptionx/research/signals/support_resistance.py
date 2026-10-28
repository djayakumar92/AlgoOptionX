"""Scored, multi-source support/resistance zones -- combines price
structure, options, and technical levels already computed elsewhere in this
app into weighted zones, per the requirement doc's §11-13 ("zones, not
single-price lines", each with a 0-100 strength score).

Deliberately built only from real, already-computed sources in this
codebase: swing points and previous day/week highs-lows
(`market_structure.py`), the HLC engine's own resistance/support bands
(`hlc_strategy.py`), VWAP (`trend.py`), OI walls (`oi_walls.py`), and classic
floor-trader pivots (cheap, computed here from data already at hand). Not
included, on purpose: volume profile and anchored VWAP are real additional
work not started here; Fibonacci was never evaluated by this project's
domain research, so it isn't added on an unverified assumption; gamma-
weighting the OI walls is a natural future upgrade, not done in this pass.

Weights below are a first, documented calibration, not a precisely-sourced
number -- same honesty stance as market_structure.py's day-type thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from algooptionx.research.signals.market_structure import HIGH, SwingPoint
from algooptionx.research.signals.oi_walls import FRESH, OiWall

SUPPORT, RESISTANCE = "SUPPORT", "RESISTANCE"
INSTITUTIONAL, STRONG, MODERATE, WEAK, IGNORE = "INSTITUTIONAL", "STRONG", "MODERATE", "WEAK", "IGNORE"

_SWING_REJECTION_POINTS = 8
_PREV_DAY_POINTS = 12
_PREV_WEEK_POINTS = 10
_HLC_BAND_POINTS = 15
_OI_WALL_FRESH_POINTS = 20
_OI_WALL_STALE_POINTS = 8
_VWAP_POINTS = 8
_PIVOT_POINTS = 6


@dataclass(frozen=True)
class ZoneFactor:
    label: str
    points: float


@dataclass(frozen=True)
class Zone:
    low: float
    high: float
    kind: str  # SUPPORT | RESISTANCE
    score: float  # 0-100
    classification: str
    factors: list[ZoneFactor]


@dataclass(frozen=True)
class _Candidate:
    price: float
    kind: str
    factor: ZoneFactor


def classify_score(score: float) -> str:
    if score >= 90:
        return INSTITUTIONAL
    if score >= 75:
        return STRONG
    if score >= 60:
        return MODERATE
    if score >= 40:
        return WEAK
    return IGNORE


def classic_pivots(prev_high: float, prev_low: float, prev_close: float) -> dict[str, float]:
    """Floor-trader pivot points from the previous session's H/L/C -- a
    cheap, widely-used technical level given data this app already has."""
    pivot = (prev_high + prev_low + prev_close) / 3
    return {
        "pivot": pivot,
        "r1": 2 * pivot - prev_low,
        "r2": pivot + (prev_high - prev_low),
        "s1": 2 * pivot - prev_high,
        "s2": pivot - (prev_high - prev_low),
    }


def _gather_candidates(
    swings: Sequence[SwingPoint],
    spot_price: float,
    prev_day_high: float | None,
    prev_day_low: float | None,
    prev_week_high: float | None,
    prev_week_low: float | None,
    hlc_bands: dict | None,
    vwap: float | None,
    call_walls: Sequence[OiWall],
    put_walls: Sequence[OiWall],
    pivots: dict | None,
) -> list[_Candidate]:
    out: list[_Candidate] = []

    for s in swings:
        kind = RESISTANCE if s.kind == HIGH else SUPPORT
        out.append(_Candidate(s.price, kind, ZoneFactor(f"Price rejection ({s.label})", _SWING_REJECTION_POINTS)))

    if prev_day_high is not None:
        out.append(_Candidate(prev_day_high, RESISTANCE, ZoneFactor("Previous day high", _PREV_DAY_POINTS)))
    if prev_day_low is not None:
        out.append(_Candidate(prev_day_low, SUPPORT, ZoneFactor("Previous day low", _PREV_DAY_POINTS)))
    if prev_week_high is not None:
        out.append(_Candidate(prev_week_high, RESISTANCE, ZoneFactor("Previous week high", _PREV_WEEK_POINTS)))
    if prev_week_low is not None:
        out.append(_Candidate(prev_week_low, SUPPORT, ZoneFactor("Previous week low", _PREV_WEEK_POINTS)))

    if hlc_bands:
        for key in ("min_resistance", "max_resistance"):
            if hlc_bands.get(key) is not None:
                out.append(_Candidate(hlc_bands[key], RESISTANCE, ZoneFactor("HLC resistance band", _HLC_BAND_POINTS)))
        for key in ("min_support", "max_support"):
            if hlc_bands.get(key) is not None:
                out.append(_Candidate(hlc_bands[key], SUPPORT, ZoneFactor("HLC support band", _HLC_BAND_POINTS)))

    if vwap is not None:
        # VWAP acts as one or the other relative to current price, not both
        # at once -- support when price is trading above it, resistance below.
        kind = SUPPORT if vwap <= spot_price else RESISTANCE
        out.append(_Candidate(vwap, kind, ZoneFactor("VWAP", _VWAP_POINTS)))

    for w in call_walls:
        points = _OI_WALL_FRESH_POINTS if w.freshness == FRESH else _OI_WALL_STALE_POINTS
        label = f"{'Fresh' if w.freshness == FRESH else 'Stale'} Call OI wall"
        out.append(_Candidate(w.strike, RESISTANCE, ZoneFactor(label, points)))
    for w in put_walls:
        points = _OI_WALL_FRESH_POINTS if w.freshness == FRESH else _OI_WALL_STALE_POINTS
        label = f"{'Fresh' if w.freshness == FRESH else 'Stale'} Put OI wall"
        out.append(_Candidate(w.strike, SUPPORT, ZoneFactor(label, points)))

    if pivots:
        out.append(_Candidate(pivots["r1"], RESISTANCE, ZoneFactor("Pivot R1", _PIVOT_POINTS)))
        out.append(_Candidate(pivots["r2"], RESISTANCE, ZoneFactor("Pivot R2", _PIVOT_POINTS)))
        out.append(_Candidate(pivots["s1"], SUPPORT, ZoneFactor("Pivot S1", _PIVOT_POINTS)))
        out.append(_Candidate(pivots["s2"], SUPPORT, ZoneFactor("Pivot S2", _PIVOT_POINTS)))

    return out


def _cluster(candidates: list[_Candidate], tolerance: float) -> list[list[_Candidate]]:
    """Candidates within tolerance of a cluster's running average price join
    it; anything farther starts a new cluster. Average-based (not
    nearest-neighbour-chained) so a cluster can't slowly drift wider than
    tolerance over a long run of closely-spaced points."""
    ordered = sorted(candidates, key=lambda c: c.price)
    clusters: list[list[_Candidate]] = []
    for c in ordered:
        if clusters:
            avg = sum(x.price for x in clusters[-1]) / len(clusters[-1])
            if abs(c.price - avg) <= tolerance:
                clusters[-1].append(c)
                continue
        clusters.append([c])
    return clusters


def build_zones(
    *,
    swings: Sequence[SwingPoint] = (),
    spot_price: float,
    prev_day_high: float | None = None,
    prev_day_low: float | None = None,
    prev_week_high: float | None = None,
    prev_week_low: float | None = None,
    hlc_bands: dict | None = None,
    vwap: float | None = None,
    call_walls: Sequence[OiWall] = (),
    put_walls: Sequence[OiWall] = (),
    pivots: dict | None = None,
    cluster_tolerance_pct: float = 0.003,
    max_zones_per_side: int = 5,
) -> list[Zone]:
    """Clusters every candidate level within cluster_tolerance_pct of spot
    price into zones (support and resistance built separately -- a level
    doesn't act as both at once), summing each cluster's factor points into
    a 0-100 score (capped). Returns at most max_zones_per_side zones per
    side, strongest first within each side, then the combined list ordered
    by price so it reads top-to-bottom like a real price ladder."""
    candidates = _gather_candidates(
        swings, spot_price, prev_day_high, prev_day_low, prev_week_high, prev_week_low,
        hlc_bands, vwap, call_walls, put_walls, pivots,
    )
    tolerance = spot_price * cluster_tolerance_pct

    zones: list[Zone] = []
    for kind in (SUPPORT, RESISTANCE):
        side = [c for c in candidates if c.kind == kind]
        for cluster in _cluster(side, tolerance):
            prices = [c.price for c in cluster]
            factors = [c.factor for c in cluster]
            score = min(100.0, sum(f.points for f in factors))
            zones.append(
                Zone(
                    low=min(prices), high=max(prices), kind=kind,
                    score=round(score, 1), classification=classify_score(score),
                    factors=factors,
                )
            )

    supports = sorted([z for z in zones if z.kind == SUPPORT], key=lambda z: z.score, reverse=True)[:max_zones_per_side]
    resistances = sorted([z for z in zones if z.kind == RESISTANCE], key=lambda z: z.score, reverse=True)[:max_zones_per_side]
    return sorted(supports + resistances, key=lambda z: (z.low + z.high) / 2)

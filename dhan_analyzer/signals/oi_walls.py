"""OI-wall detection: which strikes' open interest is a real, fresh
resistance/support signal vs. a stale or unconfirmed one.

Per `.claude/skills/nifty-options-domain-knowledge/references/
oi-pcr-institutional-practice.md` §3 (loaded before writing this): raw "top
OI strikes" (already in `sentiment.py`'s `top_call_oi_strikes`/
`top_put_oi_strikes`) is a reasonable starting point, but professional desks
weight OI *change* (today's fresh buildup vs. a level that's simply been
sitting there for days) and use volume-to-OI ratio as a signal-quality
filter: high volume + rising OI is fresh conviction, high volume + falling
OI is a specific warning that a wall may be about to break. This module adds
exactly that on top of the existing top-strikes logic -- not a new
mechanism, the concrete extension the research recommended.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

CALL, PUT = "CE", "PE"
FRESH, STALE = "FRESH", "STALE"

# A strike's volume/OI ratio counted as "meaningful activity today" rather
# than noise -- e.g. 0.15 means at least 15% of the open interest changed
# hands today. A first calibration, not a precisely-sourced number.
_HIGH_VOLUME_RATIO = 0.15
_FRESH_OI_CHANGE_PCT = 0.05  # +/-5% OI change vs. yesterday to call it fresh/unwinding


@dataclass(frozen=True)
class OiWall:
    strike: float
    option_type: str  # CE | PE
    oi: float
    oi_change: float  # today's oi - prev_day_oi
    oi_change_pct: float | None  # None if prev_day_oi is missing/zero
    volume: float
    freshness: str  # FRESH | STALE
    unwinding_warning: bool  # high volume + falling OI -- wall may be about to break


def _freshness(oi_change_pct: float | None, volume: float, oi: float) -> tuple[str, bool]:
    v_oi_ratio = (volume / oi) if oi else 0.0
    high_volume = v_oi_ratio >= _HIGH_VOLUME_RATIO
    if oi_change_pct is not None and high_volume:
        if oi_change_pct <= -_FRESH_OI_CHANGE_PCT:
            return STALE, True  # aggressive unwinding -- the specific "about to break" warning
        if oi_change_pct >= _FRESH_OI_CHANGE_PCT:
            return FRESH, False
    return STALE, False


def detect_walls(
    chain: pd.DataFrame, spot_price: float, top_n: int = 3, strike_range_pct: float = 0.06
) -> tuple[list[OiWall], list[OiWall]]:
    """Top-N Call OI strikes (potential resistance) and Put OI strikes
    (potential support), restricted to strikes within strike_range_pct of
    spot -- a far-OTM wall many strikes away is rarely relevant intraday.
    Returns (call_walls, put_walls), each sorted by OI descending."""
    if chain.empty or "oi" not in chain.columns:
        return [], []

    lo, hi = spot_price * (1 - strike_range_pct), spot_price * (1 + strike_range_pct)
    nearby = chain[(chain["strike"] >= lo) & (chain["strike"] <= hi)]

    def _walls(option_type: str) -> list[OiWall]:
        rows = nearby[(nearby["option_type"] == option_type) & nearby["oi"].notna()]
        rows = rows.nlargest(top_n, "oi")
        walls = []
        for _, row in rows.iterrows():
            oi = float(row["oi"])
            prev_oi_raw = row.get("prev_day_oi")
            prev_oi = float(prev_oi_raw) if pd.notna(prev_oi_raw) else None
            oi_change = (oi - prev_oi) if prev_oi is not None else 0.0
            oi_change_pct = (oi_change / prev_oi) if prev_oi else None
            volume_raw = row.get("volume")
            volume = float(volume_raw) if pd.notna(volume_raw) else 0.0
            freshness, warning = _freshness(oi_change_pct, volume, oi)
            walls.append(
                OiWall(
                    strike=float(row["strike"]),
                    option_type=option_type,
                    oi=oi,
                    oi_change=oi_change,
                    oi_change_pct=round(oi_change_pct, 4) if oi_change_pct is not None else None,
                    volume=volume,
                    freshness=freshness,
                    unwinding_warning=warning,
                )
            )
        return walls

    return _walls(CALL), _walls(PUT)

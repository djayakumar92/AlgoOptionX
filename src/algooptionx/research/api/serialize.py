"""Turns a pipeline.CycleResult into a JSON-safe dict for GET /api/live/state.

Kept separate from app.py so the "which fields does the frontend get" question
lives in one place. Mirrors what web_dashboard.py rendered: the metrics row,
suggestion panel, sentiment panel, and an ATM +/- strike_window chain table.
"""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from algooptionx.research.pipeline import CycleResult
from algooptionx.research.signals.hlc_strategy import HlcResult
from algooptionx.research.signals.market_structure import MarketStructureSummary


def _chain_window(chain: pd.DataFrame, spot_price: float, strike_window: int) -> tuple[list[dict], float | None]:
    if chain.empty:
        return [], None

    strikes = sorted(chain["strike"].unique())
    atm = min(strikes, key=lambda s: abs(s - spot_price))
    idx = strikes.index(atm)
    window_strikes = strikes[max(0, idx - strike_window) : idx + strike_window + 1]

    rows = []
    for strike in window_strikes:
        ce = chain[(chain["strike"] == strike) & (chain["option_type"] == "CE")]
        pe = chain[(chain["strike"] == strike) & (chain["option_type"] == "PE")]
        def _num(row: pd.DataFrame, field: str, cast=float):
            if row.empty or pd.isna(row.iloc[0][field]):
                return None
            return cast(row.iloc[0][field])

        rows.append(
            {
                # chain["strike"]/atm are numpy.float64/numpy.bool_ (from
                # pandas .unique()/comparisons) -- cast to native types, since
                # FastAPI's jsonable_encoder can't serialize numpy scalars.
                "strike": float(strike),
                "is_atm": bool(strike == atm),
                "ce_oi": _num(ce, "oi", int),
                "ce_ltp": _num(ce, "ltp"),
                "pe_ltp": _num(pe, "ltp"),
                "pe_oi": _num(pe, "oi", int),
                # Not shown on the Live page's compact table -- these feed the
                # Option Intelligence page's deeper per-strike view instead.
                "ce_iv": _num(ce, "iv"),
                "pe_iv": _num(pe, "iv"),
                "ce_volume": _num(ce, "volume", int),
                "pe_volume": _num(pe, "volume", int),
                "ce_delta": _num(ce, "delta"),
                "pe_delta": _num(pe, "delta"),
                "ce_bid": _num(ce, "bid"),
                "ce_ask": _num(ce, "ask"),
                "pe_bid": _num(pe, "bid"),
                "pe_ask": _num(pe, "ask"),
            }
        )
    return rows, float(atm)


def serialize_cycle(cycle: CycleResult, strike_window: int) -> dict:
    chain_rows, atm = _chain_window(cycle.chain, cycle.spot_price, strike_window)
    return {
        "ts": cycle.ts,
        "spot_price": cycle.spot_price,
        "atm_strike": atm,
        "sentiment": asdict(cycle.sentiment),
        "oi_behavior": {
            "call_long_buildup_count": cycle.oi_behavior.call_long_buildup_count,
            "put_long_buildup_count": cycle.oi_behavior.put_long_buildup_count,
            "call_short_buildup_count": cycle.oi_behavior.call_short_buildup_count,
            "put_short_buildup_count": cycle.oi_behavior.put_short_buildup_count,
            "bias_lean": cycle.oi_behavior.bias_lean,
        },
        "trend": asdict(cycle.trend),
        "momentum": asdict(cycle.momentum),
        "suggestion": asdict(cycle.suggestion),
        "chain": chain_rows,
    }


def serialize_hlc(result: HlcResult) -> dict:
    # All-native-Python-float dataclasses (option_ohlc.py builds them via max()/min()
    # over already-float-cast rows), so asdict() alone is JSON-safe here -- unlike
    # serialize_cycle's chain rows, this path never touches pandas/numpy. asdict()
    # recurses into trade_plan/legs too, since those are plain dataclasses as well.
    return asdict(result)


def serialize_support_resistance(zones, call_walls, put_walls) -> dict:
    # zones: list[support_resistance.Zone], call_walls/put_walls: list[oi_walls.OiWall]
    # -- all plain dataclasses of native types already, same asdict() reasoning as above.
    return {
        "zones": [asdict(z) for z in zones],
        "call_walls": [asdict(w) for w in call_walls],
        "put_walls": [asdict(w) for w in put_walls],
    }


def serialize_risk(daily_status, sizing, leg_estimates: list[dict]) -> dict:
    # sizing.risk_assessment already carries the time-of-day/expiry read, so
    # asdict(sizing) alone covers it -- no need to duplicate it at the top
    # level. Same asdict() reasoning as the other serializers in this file.
    return {
        "daily_risk": asdict(daily_status),
        "position_sizing": asdict(sizing),
        "leg_estimates": leg_estimates,
    }


def serialize_market_structure(summary: MarketStructureSummary) -> dict:
    # All fields are already plain Python dataclasses/str/float/int (see
    # market_structure.py -- every numpy/pandas value is cast before it
    # reaches these dataclasses), so asdict() alone is JSON-safe, same as
    # serialize_hlc.
    return asdict(summary)


def serialize_journal_entry(row) -> dict:
    """row: a sqlite3.Row from repository.get_journal_entries -- Row supports
    dict(row) directly since db.connect() sets row_factory=sqlite3.Row."""
    return dict(row)


def serialize_prediction(read) -> dict:
    """read: api.prediction.PredictionRead.

    `gex.per_strike` is dropped on the way out: it is one row per strike per
    request and nothing on the page plots it, while the summary fields it
    feeds (the flip level, the two walls, the regime) are all kept. Same
    asdict() reasoning as the other serializers -- every value in these
    dataclasses is cast to a native type before it gets there.
    """
    payload = {
        "as_of": read.as_of,
        "spot_price": read.spot_price,
        "unavailable": read.unavailable,
        "regime": asdict(read.regime) if read.regime else None,
        "structure": asdict(read.structure) if read.structure else None,
        "risk": asdict(read.risk_assessment) if read.risk_assessment else None,
        "signals": [asdict(s) for s in read.signals],
        "best": asdict(read.best) if read.best else None,
        "key_levels": [asdict(level) for level in read.key_levels],
        "scenarios": asdict(read.scenarios) if read.scenarios else None,
    }
    if read.gex:
        gex_payload = asdict(read.gex)
        gex_payload.pop("per_strike", None)
        payload["gex"] = gex_payload
    else:
        payload["gex"] = None
    return payload


def serialize_learning(records, regime_report) -> dict:
    """records: list[calibration.SetupRecord]; regime_report: RegimeReport."""
    return {
        "setups": [asdict(r) for r in records],
        "regime_check": asdict(regime_report),
    }

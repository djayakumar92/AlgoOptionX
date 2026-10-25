from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SentimentSummary:
    pcr_oi: float | None
    pcr_volume: float | None
    max_pain_strike: float | None
    call_iv_atm: float | None
    put_iv_atm: float | None
    iv_skew: float | None  # put_iv - call_iv near ATM; positive = puts richer (bearish skew)
    top_call_oi_strikes: list[float]
    top_put_oi_strikes: list[float]
    bias_lean: str  # BULLISH | BEARISH | NEUTRAL, from PCR alone


def _pcr(chain: pd.DataFrame, field: str) -> float | None:
    ce_total = chain.loc[chain["option_type"] == "CE", field].sum()
    pe_total = chain.loc[chain["option_type"] == "PE", field].sum()
    if not ce_total:
        return None
    return round(pe_total / ce_total, 3)


def max_pain(chain: pd.DataFrame) -> float | None:
    """Strike at which total option-writer payout (loss) is minimized.

    For each candidate expiry strike S, sum intrinsic value owed to CE holders
    struck below S plus PE holders struck above S, weighted by OI; the strike
    minimizing this sum is the "max pain" point price tends to gravitate toward
    into expiry (a widely used, though not guaranteed, options heuristic).
    """
    strikes = sorted(chain["strike"].unique())
    if not strikes:
        return None

    ce = chain[chain["option_type"] == "CE"].set_index("strike")["oi"].fillna(0)
    pe = chain[chain["option_type"] == "PE"].set_index("strike")["oi"].fillna(0)

    best_strike, best_pain = None, None
    for s in strikes:
        ce_pain = ((s - ce.index[ce.index < s]) * ce[ce.index < s]).sum() if (ce.index < s).any() else 0
        pe_pain = ((pe.index[pe.index > s] - s) * pe[pe.index > s]).sum() if (pe.index > s).any() else 0
        total = ce_pain + pe_pain
        if best_pain is None or total < best_pain:
            best_pain, best_strike = total, s
    return best_strike


def _nearest_strike(chain: pd.DataFrame, spot: float) -> float | None:
    strikes = chain["strike"].unique()
    if len(strikes) == 0:
        return None
    return min(strikes, key=lambda s: abs(s - spot))


def summarize(chain: pd.DataFrame, spot_price: float, top_n: int = 3) -> SentimentSummary:
    pcr_oi = _pcr(chain, "oi")
    pcr_volume = _pcr(chain, "volume")

    atm_strike = _nearest_strike(chain, spot_price)
    call_iv_atm = put_iv_atm = iv_skew = None
    if atm_strike is not None:
        ce_row = chain[(chain["strike"] == atm_strike) & (chain["option_type"] == "CE")]
        pe_row = chain[(chain["strike"] == atm_strike) & (chain["option_type"] == "PE")]
        if not ce_row.empty:
            call_iv_atm = float(ce_row.iloc[0]["iv"]) if pd.notna(ce_row.iloc[0]["iv"]) else None
        if not pe_row.empty:
            put_iv_atm = float(pe_row.iloc[0]["iv"]) if pd.notna(pe_row.iloc[0]["iv"]) else None
        if call_iv_atm is not None and put_iv_atm is not None:
            iv_skew = round(put_iv_atm - call_iv_atm, 3)

    top_calls = (
        chain[chain["option_type"] == "CE"].nlargest(top_n, "oi")["strike"].tolist()
        if not chain.empty
        else []
    )
    top_puts = (
        chain[chain["option_type"] == "PE"].nlargest(top_n, "oi")["strike"].tolist()
        if not chain.empty
        else []
    )

    bias_lean = "NEUTRAL"
    if pcr_oi is not None:
        if pcr_oi > 1.2:
            bias_lean = "BULLISH"  # more put OI written -> support building below
        elif pcr_oi < 0.8:
            bias_lean = "BEARISH"  # more call OI written -> resistance building above

    return SentimentSummary(
        pcr_oi=pcr_oi,
        pcr_volume=pcr_volume,
        max_pain_strike=max_pain(chain),
        call_iv_atm=call_iv_atm,
        put_iv_atm=put_iv_atm,
        iv_skew=iv_skew,
        top_call_oi_strikes=top_calls,
        top_put_oi_strikes=top_puts,
        bias_lean=bias_lean,
    )

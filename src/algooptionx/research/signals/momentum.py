from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MomentumSummary:
    rsi: float | None
    rsi_state: str  # OVERBOUGHT | OVERSOLD | NEUTRAL
    roc: float | None
    iv_rank: float | None  # 0-100, percentile of current ATM IV within session's observed range
    bias_lean: str  # BULLISH | BEARISH | NEUTRAL


def rsi(candles: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = candles["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    # avg_loss == 0 means no losses in the lookback -> RSI is 100 (not NaN);
    # avg_gain == 0 (and avg_loss > 0) -> RSI is 0. Handle both before dividing.
    result = pd.Series(np.where(avg_loss == 0, 100.0, np.nan), index=candles.index)
    needs_calc = avg_loss != 0
    rs = avg_gain[needs_calc] / avg_loss[needs_calc]
    result[needs_calc] = 100 - (100 / (1 + rs))
    result[avg_gain.isna() | avg_loss.isna()] = np.nan
    return result


def rate_of_change(candles: pd.DataFrame, period: int = 10) -> pd.Series:
    return (candles["close"] - candles["close"].shift(period)) / candles["close"].shift(period) * 100


def iv_rank(current_iv: float | None, iv_history: list[float]) -> float | None:
    """Percentile of current_iv within iv_history observed so far this session.

    Not a true 52-week IV rank (that needs a long IV history we don't persist at
    tick granularity in Phase 1) -- scoped intentionally to what's cheaply available
    from accumulated option-chain polls during the current run.
    """
    if current_iv is None or len(iv_history) < 5:
        return None
    arr = np.array(iv_history)
    return round(float((arr < current_iv).mean() * 100), 1)


def summarize(
    candles: pd.DataFrame,
    current_atm_iv: float | None = None,
    iv_history: list[float] | None = None,
    rsi_period: int = 14,
    roc_period: int = 10,
) -> MomentumSummary:
    if len(candles) < rsi_period + 1:
        return MomentumSummary(None, "NEUTRAL", None, None, "NEUTRAL")

    rsi_series = rsi(candles, rsi_period)
    roc_series = rate_of_change(candles, roc_period)

    last_rsi = rsi_series.iloc[-1]
    last_roc = roc_series.iloc[-1]

    rsi_state = "NEUTRAL"
    if pd.notna(last_rsi):
        if last_rsi >= 70:
            rsi_state = "OVERBOUGHT"
        elif last_rsi <= 30:
            rsi_state = "OVERSOLD"

    # ROC (trend-following) is the primary driver; RSI oversold/overbought (a
    # contrarian/reversal signal) only breaks ties when ROC is flat or unavailable,
    # rather than fighting a clear ROC reading into a NEUTRAL cancellation.
    bias_lean = "NEUTRAL"
    if pd.notna(last_roc) and last_roc > 0:
        bias_lean = "BULLISH"
    elif pd.notna(last_roc) and last_roc < 0:
        bias_lean = "BEARISH"
    elif rsi_state == "OVERSOLD":
        bias_lean = "BULLISH"
    elif rsi_state == "OVERBOUGHT":
        bias_lean = "BEARISH"

    return MomentumSummary(
        rsi=round(last_rsi, 2) if pd.notna(last_rsi) else None,
        rsi_state=rsi_state,
        roc=round(last_roc, 2) if pd.notna(last_roc) else None,
        iv_rank=iv_rank(current_atm_iv, iv_history or []),
        bias_lean=bias_lean,
    )

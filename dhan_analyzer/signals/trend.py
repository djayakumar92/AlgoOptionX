from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TrendSummary:
    vwap: float | None
    price_vs_vwap: str  # ABOVE | BELOW | AT
    ma_fast: float | None
    ma_slow: float | None
    ma_crossover: str  # BULLISH | BEARISH | NONE
    adx: float | None
    trend_strength: str  # STRONG | WEAK | NONE
    bias_lean: str  # BULLISH | BEARISH | NEUTRAL


def vwap(candles: pd.DataFrame) -> pd.Series:
    """Volume-weighted average price, **reset at the start of each session**.

    The reset is the whole definition. VWAP is "the average price paid so far
    today"; a cumulative sum that never restarts is an average over however
    much history happens to be loaded, which is a different and far less
    useful number.

    This ran without the reset until it was caught live: with roughly twenty
    sessions of 5-minute bars in memory, it reported the day's average price
    as 24,100 while NIFTY was trading at 23,779 -- 321 points adrift, and
    shown on screen under the label "Day's average price". It also gates the
    trend-pullback setup, which asks whether price has come back to that
    level, so a stale value there does not merely mislabel a number, it
    changes which trades the engine offers.

    Falls back to a single cumulative run when the frame carries no `ts`
    column to group on, which is only the case for hand-built test frames.
    """
    typical_price = (candles["high"] + candles["low"] + candles["close"]) / 3
    price_volume = typical_price * candles["volume"]

    if "ts" in candles.columns:
        session = pd.to_datetime(candles["ts"], unit="s").dt.date
        cum_vol = candles["volume"].groupby(session).cumsum()
        cum_pv = price_volume.groupby(session).cumsum()
    else:
        cum_vol = candles["volume"].cumsum()
        cum_pv = price_volume.cumsum()

    return cum_pv / cum_vol.replace(0, np.nan)


def moving_average(candles: pd.DataFrame, window: int) -> pd.Series:
    return candles["close"].rolling(window).mean()


def adx(candles: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = candles["high"], candles["low"], candles["close"]

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=candles.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=candles.index).ewm(alpha=1 / period, adjust=False).mean() / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def summarize(candles: pd.DataFrame, fast: int = 9, slow: int = 21, adx_period: int = 14) -> TrendSummary:
    if len(candles) < slow + 1:
        return TrendSummary(None, "AT", None, None, "NONE", None, "NONE", "NEUTRAL")

    vwap_series = vwap(candles)
    ma_fast_series = moving_average(candles, fast)
    ma_slow_series = moving_average(candles, slow)
    adx_series = adx(candles, adx_period)

    last_close = candles["close"].iloc[-1]
    last_vwap = vwap_series.iloc[-1]
    last_ma_fast = ma_fast_series.iloc[-1]
    last_ma_slow = ma_slow_series.iloc[-1]
    prev_ma_fast = ma_fast_series.iloc[-2]
    prev_ma_slow = ma_slow_series.iloc[-2]
    last_adx = adx_series.iloc[-1]

    price_vs_vwap = "AT"
    if pd.notna(last_vwap):
        if last_close > last_vwap:
            price_vs_vwap = "ABOVE"
        elif last_close < last_vwap:
            price_vs_vwap = "BELOW"

    crossover = "NONE"
    if pd.notna(last_ma_fast) and pd.notna(last_ma_slow) and pd.notna(prev_ma_fast) and pd.notna(prev_ma_slow):
        if prev_ma_fast <= prev_ma_slow and last_ma_fast > last_ma_slow:
            crossover = "BULLISH"
        elif prev_ma_fast >= prev_ma_slow and last_ma_fast < last_ma_slow:
            crossover = "BEARISH"
        elif last_ma_fast > last_ma_slow:
            crossover = "BULLISH"
        elif last_ma_fast < last_ma_slow:
            crossover = "BEARISH"

    trend_strength = "NONE"
    if pd.notna(last_adx):
        trend_strength = "STRONG" if last_adx >= 25 else "WEAK"

    bias_votes = [v for v in (price_vs_vwap == "ABOVE", crossover == "BULLISH") if v is True]
    bear_votes = [v for v in (price_vs_vwap == "BELOW", crossover == "BEARISH") if v is True]
    if len(bias_votes) > len(bear_votes):
        bias_lean = "BULLISH"
    elif len(bear_votes) > len(bias_votes):
        bias_lean = "BEARISH"
    else:
        bias_lean = "NEUTRAL"

    # float(round(...)), not round(...): these are numpy scalars, and
    # round() on a numpy float returns a numpy float. Any comparison against
    # one then produces a numpy bool, which json.dumps refuses -- that leaked
    # all the way out to a 500 on the prediction endpoint.
    return TrendSummary(
        vwap=float(round(last_vwap, 2)) if pd.notna(last_vwap) else None,
        price_vs_vwap=price_vs_vwap,
        ma_fast=float(round(last_ma_fast, 2)) if pd.notna(last_ma_fast) else None,
        ma_slow=float(round(last_ma_slow, 2)) if pd.notna(last_ma_slow) else None,
        ma_crossover=crossover,
        adx=float(round(last_adx, 2)) if pd.notna(last_adx) else None,
        trend_strength=trend_strength,
        bias_lean=bias_lean,
    )

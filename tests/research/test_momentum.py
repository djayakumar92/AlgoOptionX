import numpy as np
import pandas as pd

from algooptionx.research.signals import momentum


def _uptrend_candles(n: int = 30) -> pd.DataFrame:
    closes = 100 + np.arange(n) * 0.5
    return pd.DataFrame(
        {
            "ts": np.arange(n),
            "open": closes - 0.2,
            "high": closes + 0.3,
            "low": closes - 0.3,
            "close": closes,
            "volume": np.full(n, 1000),
        }
    )


def test_insufficient_data_returns_none_summary():
    summary = momentum.summarize(_uptrend_candles(5))
    assert summary.rsi is None
    assert summary.bias_lean == "NEUTRAL"


def test_uptrend_yields_high_rsi_and_bullish_lean():
    summary = momentum.summarize(_uptrend_candles(30))
    assert summary.rsi > 50
    assert summary.roc > 0
    assert summary.bias_lean == "BULLISH"


def test_iv_rank_needs_minimum_history():
    assert momentum.iv_rank(15.0, [10, 11, 12]) is None  # fewer than 5 samples
    assert momentum.iv_rank(15.0, [5, 10, 12, 14, 20]) == 80.0

import numpy as np
import pandas as pd

from dhan_analyzer.signals import trend


def _uptrend_candles(n: int = 40) -> pd.DataFrame:
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
    summary = trend.summarize(_uptrend_candles(5))
    assert summary.vwap is None
    assert summary.bias_lean == "NEUTRAL"


def test_uptrend_yields_bullish_lean_and_price_above_vwap():
    summary = trend.summarize(_uptrend_candles(40))
    assert summary.price_vs_vwap == "ABOVE"
    assert summary.ma_crossover == "BULLISH"
    assert summary.bias_lean == "BULLISH"


def test_downtrend_yields_bearish_lean():
    candles = _uptrend_candles(40).iloc[::-1].reset_index(drop=True)
    candles["ts"] = np.arange(len(candles))
    summary = trend.summarize(candles)
    assert summary.bias_lean == "BEARISH"


def test_vwap_resets_each_session():
    """VWAP means "the average price paid so far today". Without a daily
    reset it reported 24,100 while NIFTY traded at 23,779 -- caught on a live
    run, and it gates the trend-pullback setup as well as being displayed."""
    from datetime import datetime, timedelta

    import pandas as pd

    from dhan_analyzer.signals.trend import vwap

    rows = []
    # Yesterday, traded heavily around 24,100.
    day_one = datetime(2026, 9, 4, 9, 15)
    for i in range(20):
        rows.append({"ts": int((day_one + timedelta(minutes=5 * i)).timestamp()),
                     "high": 24110.0, "low": 24090.0, "close": 24100.0, "volume": 100_000})
    # Today, trading around 23,780.
    day_two = datetime(2026, 9, 5, 9, 15)
    for i in range(6):
        rows.append({"ts": int((day_two + timedelta(minutes=5 * i)).timestamp()),
                     "high": 23790.0, "low": 23770.0, "close": 23780.0, "volume": 100_000})

    series = vwap(pd.DataFrame(rows))
    # Today's VWAP must reflect today, not a blend of both sessions.
    assert 23770 <= series.iloc[-1] <= 23790
    # ...and the first bar of a session is its own VWAP.
    assert abs(series.iloc[20] - 23780.0) < 1.0

import pandas as pd

from dhan_analyzer.signals import sentiment


def _chain():
    return pd.DataFrame(
        [
            {"strike": 24800, "option_type": "CE", "oi": 1000, "volume": 500, "ltp": 150, "iv": 12.0},
            {"strike": 24800, "option_type": "PE", "oi": 4000, "volume": 2000, "ltp": 90, "iv": 14.0},
            {"strike": 24900, "option_type": "CE", "oi": 3000, "volume": 1000, "ltp": 100, "iv": 11.5},
            {"strike": 24900, "option_type": "PE", "oi": 1000, "volume": 400, "ltp": 60, "iv": 13.0},
        ]
    )


def test_pcr_oi_bullish_when_puts_dominate():
    summary = sentiment.summarize(_chain(), spot_price=24850)
    assert summary.pcr_oi == round((4000 + 1000) / (1000 + 3000), 3)
    assert summary.bias_lean == "BULLISH"


def test_pcr_oi_neutral_when_balanced():
    chain = _chain()
    chain.loc[chain["option_type"] == "PE", "oi"] = chain.loc[chain["option_type"] == "CE", "oi"].values
    summary = sentiment.summarize(chain, spot_price=24850)
    assert summary.pcr_oi == 1.0
    assert summary.bias_lean == "NEUTRAL"


def test_max_pain_prefers_high_oi_strike_cluster():
    chain = pd.DataFrame(
        [
            {"strike": 100, "option_type": "CE", "oi": 10, "volume": 0, "ltp": 1, "iv": 10},
            {"strike": 100, "option_type": "PE", "oi": 10, "volume": 0, "ltp": 1, "iv": 10},
            {"strike": 110, "option_type": "CE", "oi": 1000, "volume": 0, "ltp": 1, "iv": 10},
            {"strike": 110, "option_type": "PE", "oi": 1000, "volume": 0, "ltp": 1, "iv": 10},
            {"strike": 120, "option_type": "CE", "oi": 10, "volume": 0, "ltp": 1, "iv": 10},
            {"strike": 120, "option_type": "PE", "oi": 10, "volume": 0, "ltp": 1, "iv": 10},
        ]
    )
    assert sentiment.max_pain(chain) == 110


def test_atm_iv_and_skew():
    summary = sentiment.summarize(_chain(), spot_price=24800)
    assert summary.call_iv_atm == 12.0
    assert summary.put_iv_atm == 14.0
    assert summary.iv_skew == 2.0

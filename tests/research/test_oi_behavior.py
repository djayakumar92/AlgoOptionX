import pandas as pd

from algooptionx.research.signals import oi_behavior


def test_classify_all_four_quadrants():
    previous = pd.DataFrame(
        [
            {"strike": 100, "option_type": "CE", "ltp": 10, "oi": 1000},  # -> long buildup
            {"strike": 200, "option_type": "CE", "ltp": 10, "oi": 1000},  # -> short covering
            {"strike": 300, "option_type": "PE", "ltp": 10, "oi": 1000},  # -> short buildup
            {"strike": 400, "option_type": "PE", "ltp": 10, "oi": 1000},  # -> long unwinding
        ]
    )
    latest = pd.DataFrame(
        [
            {"strike": 100, "option_type": "CE", "ltp": 15, "oi": 1500},
            {"strike": 200, "option_type": "CE", "ltp": 15, "oi": 500},
            {"strike": 300, "option_type": "PE", "ltp": 5, "oi": 1500},
            {"strike": 400, "option_type": "PE", "ltp": 5, "oi": 500},
        ]
    )

    result = oi_behavior.classify(latest, previous)
    by_strike = result.per_contract.set_index("strike")["behavior"].to_dict()

    assert by_strike[100] == oi_behavior.LONG_BUILDUP
    assert by_strike[200] == oi_behavior.SHORT_COVERING
    assert by_strike[300] == oi_behavior.SHORT_BUILDUP
    assert by_strike[400] == oi_behavior.LONG_UNWINDING


def test_classify_with_no_previous_snapshot_returns_neutral_summary():
    latest = pd.DataFrame([{"strike": 100, "option_type": "CE", "ltp": 15, "oi": 1500}])
    result = oi_behavior.classify(latest, None)
    assert result.per_contract.empty
    assert result.bias_lean == "NEUTRAL"


def test_bias_lean_follows_dominant_long_buildup_side():
    previous = pd.DataFrame(
        [
            {"strike": 100, "option_type": "PE", "ltp": 10, "oi": 1000},
            {"strike": 200, "option_type": "PE", "ltp": 10, "oi": 1000},
            {"strike": 300, "option_type": "CE", "ltp": 10, "oi": 1000},
        ]
    )
    latest = pd.DataFrame(
        [
            {"strike": 100, "option_type": "PE", "ltp": 15, "oi": 1500},  # long buildup
            {"strike": 200, "option_type": "PE", "ltp": 15, "oi": 1500},  # long buildup
            {"strike": 300, "option_type": "CE", "ltp": 15, "oi": 1500},  # long buildup
        ]
    )
    result = oi_behavior.classify(latest, previous)
    assert result.put_long_buildup_count == 2
    assert result.call_long_buildup_count == 1
    assert result.bias_lean == "BULLISH"

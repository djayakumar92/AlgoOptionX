import pandas as pd

from algooptionx.research.signals.oi_walls import FRESH, STALE, detect_walls


def _row(strike, option_type, oi, prev_day_oi, volume):
    return {
        "strike": strike,
        "option_type": option_type,
        "oi": oi,
        "prev_day_oi": prev_day_oi,
        "volume": volume,
    }


def test_detect_walls_picks_top_n_within_range_by_oi():
    rows = [
        _row(24000, "CE", 100_000, 100_000, 1000),
        _row(24050, "CE", 500_000, 500_000, 1000),  # highest OI, should rank first
        _row(24100, "CE", 200_000, 200_000, 1000),
        _row(30000, "CE", 900_000, 900_000, 1000),  # far outside strike_range_pct -- excluded
    ]
    chain = pd.DataFrame(rows)
    calls, puts = detect_walls(chain, spot_price=24050, top_n=2, strike_range_pct=0.06)
    assert puts == []
    assert [w.strike for w in calls] == [24050, 24100]


def test_detect_walls_fresh_high_volume_rising_oi():
    rows = [_row(24050, "PE", 550_000, 500_000, 100_000)]  # +10% OI, volume/OI ~18%
    chain = pd.DataFrame(rows)
    calls, puts = detect_walls(chain, spot_price=24050)
    assert puts[0].freshness == FRESH
    assert puts[0].unwinding_warning is False


def test_detect_walls_stale_high_volume_falling_oi_warns_unwinding():
    rows = [_row(24050, "CE", 450_000, 500_000, 100_000)]  # -10% OI, volume/OI 22%
    chain = pd.DataFrame(rows)
    calls, puts = detect_walls(chain, spot_price=24050)
    assert calls[0].freshness == STALE
    assert calls[0].unwinding_warning is True


def test_detect_walls_low_volume_stays_stale_even_with_oi_change():
    rows = [_row(24050, "CE", 550_000, 500_000, 1000)]  # +10% OI but volume/OI ~0.2%, not "high volume"
    chain = pd.DataFrame(rows)
    calls, puts = detect_walls(chain, spot_price=24050)
    assert calls[0].freshness == STALE
    assert calls[0].unwinding_warning is False


def test_detect_walls_missing_prev_day_oi_degrades_gracefully():
    rows = [_row(24050, "PE", 500_000, None, 100_000)]
    chain = pd.DataFrame(rows)
    calls, puts = detect_walls(chain, spot_price=24050)
    assert puts[0].oi_change_pct is None
    assert puts[0].freshness == STALE
    assert puts[0].unwinding_warning is False


def test_detect_walls_empty_chain_returns_empty():
    assert detect_walls(pd.DataFrame(), spot_price=24050) == ([], [])

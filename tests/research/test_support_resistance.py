from algooptionx.research.signals.market_structure import HIGH, LOW, SwingPoint
from algooptionx.research.signals.oi_walls import FRESH, STALE, OiWall
from algooptionx.research.signals.support_resistance import (
    IGNORE,
    INSTITUTIONAL,
    MODERATE,
    RESISTANCE,
    STRONG,
    SUPPORT,
    WEAK,
    build_zones,
    classic_pivots,
    classify_score,
)


def _wall(strike, option_type, fresh=True):
    return OiWall(
        strike=strike, option_type=option_type, oi=500_000, oi_change=50_000,
        oi_change_pct=0.1, volume=100_000, freshness=FRESH if fresh else STALE,
        unwinding_warning=False,
    )


# ---- classify_score --------------------------------------------------------

def test_classify_score_boundaries():
    assert classify_score(90) == INSTITUTIONAL
    assert classify_score(89.9) == STRONG
    assert classify_score(75) == STRONG
    assert classify_score(74.9) == MODERATE
    assert classify_score(60) == MODERATE
    assert classify_score(59.9) == WEAK
    assert classify_score(40) == WEAK
    assert classify_score(39.9) == IGNORE


# ---- classic_pivots ---------------------------------------------------------

def test_classic_pivots_known_values():
    pivots = classic_pivots(prev_high=110, prev_low=90, prev_close=100)
    assert pivots["pivot"] == 100
    assert pivots["r1"] == 110
    assert pivots["r2"] == 120
    assert pivots["s1"] == 90
    assert pivots["s2"] == 80


# ---- build_zones ------------------------------------------------------------

def test_build_zones_clusters_confirming_factors_and_sums_score():
    swings = [SwingPoint(ts=1, price=24100, kind=HIGH, label="HH")]  # +8
    zones = build_zones(
        swings=swings,
        spot_price=24000,
        prev_day_high=24105,  # +12
        hlc_bands={"min_resistance": 24098},  # +15
        call_walls=[_wall(24110, "CE", fresh=True)],  # +20
    )
    resistance_zones = [z for z in zones if z.kind == RESISTANCE]
    assert len(resistance_zones) == 1
    zone = resistance_zones[0]
    assert zone.score == 55  # 8 + 12 + 15 + 20
    assert zone.classification == WEAK
    assert len(zone.factors) == 4


def test_build_zones_score_capped_at_100():
    swings = [SwingPoint(ts=1, price=24100, kind=HIGH, label="HH")]  # +8
    zones = build_zones(
        swings=swings,
        spot_price=24000,
        prev_day_high=24101,  # +12
        prev_week_high=24102,  # +10
        hlc_bands={"min_resistance": 24099},  # +15
        call_walls=[_wall(24100, "CE"), _wall(24103, "CE"), _wall(24098, "CE")],  # +20 each = 60
    )
    zone = [z for z in zones if z.kind == RESISTANCE][0]
    raw_total = 8 + 12 + 10 + 15 + 60  # 105, would exceed 100 uncapped
    assert raw_total > 100
    assert zone.score == 100.0
    assert zone.classification == INSTITUTIONAL


def test_build_zones_keeps_far_apart_candidates_separate():
    swings = [
        SwingPoint(ts=1, price=24000, kind=HIGH, label="HH"),
        SwingPoint(ts=2, price=26000, kind=HIGH, label="HH"),
    ]
    zones = build_zones(swings=swings, spot_price=24000)
    resistance_zones = [z for z in zones if z.kind == RESISTANCE]
    assert len(resistance_zones) == 2
    assert {z.low for z in resistance_zones} == {24000, 26000}


def test_build_zones_vwap_support_below_spot_resistance_above():
    zones_below = build_zones(spot_price=24000, vwap=23900)
    assert zones_below[0].kind == SUPPORT

    zones_above = build_zones(spot_price=24000, vwap=24100)
    assert zones_above[0].kind == RESISTANCE


def test_build_zones_caps_max_zones_per_side():
    # 6 well-separated, equal-strength resistance candidates -- only the
    # strongest max_zones_per_side (default 5) should survive; ties keep
    # price-ascending order, so the highest one is the one dropped.
    swings = [SwingPoint(ts=i, price=24000 + i * 1000, kind=HIGH, label="HH") for i in range(6)]
    zones = build_zones(swings=swings, spot_price=24000, max_zones_per_side=5)
    resistance_zones = [z for z in zones if z.kind == RESISTANCE]
    assert len(resistance_zones) == 5
    assert max(z.low for z in resistance_zones) == 24000 + 4 * 1000


def test_build_zones_no_inputs_returns_empty():
    assert build_zones(spot_price=24000) == []

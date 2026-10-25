from datetime import datetime

from dhan_analyzer.signals.risk import (
    CLOSING,
    MIDDAY,
    OPENING,
    assess_risk,
    classify_session_window,
    daily_risk_status,
    position_sizing,
)

DAY = datetime(2026, 9, 2).date()


def _at(hh, mm, ss=0):
    return datetime(DAY.year, DAY.month, DAY.day, hh, mm, ss)


# ---- classify_session_window ------------------------------------------------

def test_classify_session_window_opening_boundary():
    assert classify_session_window(_at(9, 15)) == OPENING
    assert classify_session_window(_at(9, 45)) == OPENING  # inclusive boundary
    assert classify_session_window(_at(9, 45, 1)) == MIDDAY


def test_classify_session_window_closing_boundary():
    assert classify_session_window(_at(13, 59, 59)) == MIDDAY
    assert classify_session_window(_at(14, 0)) == CLOSING  # inclusive boundary
    assert classify_session_window(_at(15, 29)) == CLOSING


def test_classify_session_window_midday():
    assert classify_session_window(_at(11, 30)) == MIDDAY


# ---- assess_risk -------------------------------------------------------------

def test_assess_risk_midday_normal_day_is_full_size_no_avoid():
    r = assess_risk(_at(11, 30), is_expiry_day=False)
    assert r.window == MIDDAY
    assert r.size_multiplier == 1.0
    assert r.avoid_new_entries is False
    assert r.reasons == []


def test_assess_risk_opening_always_avoids_new_entries():
    r_normal = assess_risk(_at(9, 20), is_expiry_day=False)
    r_expiry = assess_risk(_at(9, 20), is_expiry_day=True)
    assert r_normal.avoid_new_entries is True
    assert r_expiry.avoid_new_entries is True
    assert len(r_normal.reasons) == 1
    assert len(r_expiry.reasons) == 1


def test_assess_risk_closing_on_expiry_is_the_worst_case():
    r = assess_risk(_at(14, 30), is_expiry_day=True)
    assert r.window == CLOSING
    assert r.avoid_new_entries is True
    assert r.size_multiplier == 0.25
    # Should be the smallest multiplier across the whole table.
    all_multipliers = [
        assess_risk(_at(9, 20), False).size_multiplier,
        assess_risk(_at(9, 20), True).size_multiplier,
        assess_risk(_at(11, 30), False).size_multiplier,
        assess_risk(_at(11, 30), True).size_multiplier,
        assess_risk(_at(14, 30), False).size_multiplier,
        r.size_multiplier,
    ]
    assert r.size_multiplier == min(all_multipliers)


# ---- position_sizing ----------------------------------------------------------

def test_position_sizing_table_math_full_size():
    risk = assess_risk(_at(11, 30), is_expiry_day=False)  # multiplier 1.0
    sizing = position_sizing(
        capital=500_000, max_risk_pct_per_trade=0.01, lot_size=65,
        risk_assessment=risk, stop_distances=(20,),
    )
    assert sizing.max_risk_per_trade == 5000
    row = sizing.table[0]
    # max_risk=5000, risk_per_lot=20*65=1300 -> floor(5000/1300)=3 lots
    assert row.lots == 3
    assert row.quantity == 195
    assert row.risk_amount == 3900


def test_position_sizing_applies_time_of_day_multiplier():
    risk = assess_risk(_at(14, 30), is_expiry_day=True)  # multiplier 0.25
    sizing = position_sizing(
        capital=500_000, max_risk_pct_per_trade=0.01, lot_size=65,
        risk_assessment=risk, stop_distances=(20,),
    )
    # Unadjusted lots would be 3; 3 * 0.25 = 0.75 -> int() truncates to 0.
    assert sizing.table[0].lots == 0


def test_position_sizing_includes_estimated_row_when_given():
    risk = assess_risk(_at(11, 30), is_expiry_day=False)
    sizing = position_sizing(
        capital=500_000, max_risk_pct_per_trade=0.01, lot_size=65,
        risk_assessment=risk, stop_distances=(20,), estimated_stop_distance=15,
    )
    assert sizing.estimated is not None
    assert sizing.estimated.stop_distance_points == 15


def test_position_sizing_zero_stop_distance_is_zero_lots_not_a_crash():
    risk = assess_risk(_at(11, 30), is_expiry_day=False)
    sizing = position_sizing(
        capital=500_000, max_risk_pct_per_trade=0.01, lot_size=65,
        risk_assessment=risk, stop_distances=(0,),
    )
    assert sizing.table[0].lots == 0


# ---- daily_risk_status ---------------------------------------------------------

def test_daily_risk_status_no_prior_graded_day():
    status = daily_risk_status(None, capital=500_000, lot_size=65, max_daily_loss_pct=0.02)
    assert status.as_of_trade_date is None
    assert status.locked is False
    assert status.remaining_budget == status.max_daily_loss == 10_000


def test_daily_risk_status_loss_reduces_remaining_budget():
    # -10 points * lot_size 65 = -650 realized amount
    status = daily_risk_status(("2026-09-01", -10.0), capital=500_000, lot_size=65, max_daily_loss_pct=0.02)
    assert status.realized_amount == -650
    assert status.remaining_budget == 10_000 - 650
    assert status.locked is False


def test_daily_risk_status_locks_when_loss_meets_daily_limit():
    # max_daily_loss = 500000*0.02 = 10000; lot_size 65 -> -10000/65 ~= -153.8 pts
    status = daily_risk_status(("2026-09-01", -160.0), capital=500_000, lot_size=65, max_daily_loss_pct=0.02)
    assert status.locked is True
    assert status.remaining_budget == 0.0


def test_daily_risk_status_gain_does_not_increase_remaining_beyond_cap():
    status = daily_risk_status(("2026-09-01", 25.0), capital=500_000, lot_size=65, max_daily_loss_pct=0.02)
    assert status.realized_amount == 1625
    assert status.remaining_budget == status.max_daily_loss  # a gain doesn't extend the budget
    assert status.locked is False

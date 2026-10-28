"""Regression test using the user's own spreadsheet's worked example as ground
truth (nifty_options_trading.xlsx, dated 20/07/2026): spot 24395.85, 3 candidate
strikes 24350/24400/24450, ATM=24450."""

from algooptionx.research.ingestion.option_ohlc import SessionOhlc
from algooptionx.research.signals.hlc_strategy import (
    BUYER,
    INDECISION,
    PANIC,
    PROFIT_BOOKING,
    SELLER,
    StrikeQuote,
    analyze,
    analyze_leg,
    build_trade_plan,
    combined_signal,
    range_band,
    range_strikes,
    select_atm,
)

CANDIDATES = [
    StrikeQuote(24350, SessionOhlc(high=186.4, close=152.85, low=113.35), SessionOhlc(high=110.35, close=63.4, low=54.4)),
    StrikeQuote(24400, SessionOhlc(high=152.8, close=122.5, low=89), SessionOhlc(high=135.75, close=82.4, low=71.25)),
    StrikeQuote(24450, SessionOhlc(high=123.8, close=95.85, low=69), SessionOhlc(high=164.5, close=105.25, low=92.2)),
]


def test_select_atm_picks_smallest_ce_pe_diff():
    atm = select_atm(CANDIDATES)
    assert atm.strike == 24450


def test_analyze_leg_buyer_domination():
    # ATM CE: high=123.8, close=95.85, low=69 -> close-high=-27.95 (Buyer)
    leg = analyze_leg(SessionOhlc(high=123.8, close=95.85, low=69))
    assert leg.domination == BUYER
    assert leg.market_type == PANIC


def test_analyze_leg_seller_domination():
    # ATM PE: high=164.5, close=105.25, low=92.2 -> close-low=13.05 (Seller)
    leg = analyze_leg(SessionOhlc(high=164.5, close=105.25, low=92.2))
    assert leg.domination == SELLER
    assert leg.market_type == PROFIT_BOOKING


def test_analyze_leg_indecision_when_neither_within_threshold():
    leg = analyze_leg(SessionOhlc(high=200, close=100, low=0))
    assert leg.domination == INDECISION


def test_analyze_leg_close_equals_high_is_indecision_not_buyer():
    # Excel's IF(...,diff<0,...) requires a strict sign, so an exact tie is
    # Indecision, not Buyer -- easy detail to miss when reading "within 35 points".
    # low=0 keeps the Seller branch (close-low far > threshold) from masking this.
    leg = analyze_leg(SessionOhlc(high=100, close=100, low=0))
    assert leg.domination == INDECISION


def test_combined_signal_matrix():
    assert combined_signal(BUYER, BUYER) == "Strong Bullish (Panic Buying)"
    assert combined_signal(SELLER, SELLER) == "Strong Bearish (Profit Booking)"
    assert combined_signal(BUYER, SELLER) == "Mixed - CE Bullish / PE Bearish"
    assert combined_signal(SELLER, BUYER) == "Mixed - CE Bearish / PE Bullish"
    assert combined_signal(INDECISION, BUYER) == "Indecision - Sideways Market"


def test_analyze_full_worked_example():
    result = analyze(CANDIDATES, session_date="2026-07-20", nifty_close=24395.85)

    assert result.session_date == "2026-07-20"
    assert result.nifty_close == 24395.85
    assert result.atm_strike == 24450
    assert result.atm_ce_close == 95.85
    assert result.atm_pe_close == 105.25

    assert round(result.max_resistance, 2) == 24651.1
    assert round(result.min_resistance, 2) == 24545.85
    assert round(result.min_support, 2) == 24344.75
    assert round(result.max_support, 2) == 24248.9

    assert result.ce.domination == BUYER
    assert result.pe.domination == SELLER
    assert result.combined_signal == "Mixed - CE Bullish / PE Bearish"


# Ground truth from a screenshot of a community "HLC daily planning" sheet
# (Telegram group "HLC Underground-2025"), confirmed field-by-field with the user:
# Weekly Close 24078.3 (Wed 2026-08-19, the day after the previous week's Tuesday
# expiry) -> range strikes 24000/24100 -> combined CE+PE premiums 255.65/234.9 ->
# sell 24255.65/24334.9, buy 23744.35/23865.1. Monthly Close 24250.2 -> strikes
# 24200/24300 -> premiums 601/588.2 -> sell 24801/24888.2, buy 23599/23711.8.


def test_range_strikes_weekly_example():
    assert range_strikes(24078.3) == (24000.0, 24100.0)


def test_range_strikes_monthly_example():
    assert range_strikes(24250.2) == (24200.0, 24300.0)


def test_range_strikes_exact_multiple_bumps_high():
    # close already a multiple of 100 -- low/high must stay distinct.
    assert range_strikes(24100.0) == (24100.0, 24200.0)


def test_range_band_weekly_example():
    band = range_band(24078.3, 24000.0, 255.65, 24100.0, 234.9)
    assert round(band.sell_low, 2) == 24255.65
    assert round(band.sell_high, 2) == 24334.9
    assert round(band.buy_low, 2) == 23744.35
    assert round(band.buy_high, 2) == 23865.1


def test_range_band_monthly_example():
    band = range_band(24250.2, 24200.0, 601.0, 24300.0, 588.2)
    assert round(band.sell_low, 2) == 24801.0
    assert round(band.sell_high, 2) == 24888.2
    assert round(band.buy_low, 2) == 23599.0
    assert round(band.buy_high, 2) == 23711.8


# ---- build_trade_plan ------------------------------------------------------


def test_trade_plan_worked_example_sells_the_seller_leg():
    # From test_analyze_full_worked_example: ce=Buyer, pe=Seller -> Mixed, sell PE.
    result = analyze(CANDIDATES, session_date="2026-07-20", nifty_close=24395.85)
    plan = build_trade_plan(result, trade_date="2026-07-21", target_points_per_day=20.0, max_trades_per_day=2)

    assert plan.session_date == "2026-07-20"
    assert plan.trade_date == "2026-07-21"
    assert len(plan.legs) == 1
    leg = plan.legs[0]
    assert leg.option_type == "PE"
    assert leg.action == "SELL"
    assert leg.strike == 24450
    assert leg.entry_trigger == 105.25
    assert leg.target_points == 20.0
    assert round(leg.target, 2) == 85.25


def test_trade_plan_strong_bearish_sells_both_legs_split_target():
    both_seller = [
        StrikeQuote(24450, SessionOhlc(high=200, close=95.85, low=90), SessionOhlc(high=200, close=105.25, low=100)),
    ]
    result = analyze(both_seller, session_date="2026-07-21", nifty_close=24450)
    assert result.ce.domination == SELLER
    assert result.pe.domination == SELLER

    plan = build_trade_plan(result, trade_date="2026-07-22", target_points_per_day=20.0, max_trades_per_day=2)

    assert len(plan.legs) == 2
    assert {leg.option_type for leg in plan.legs} == {"CE", "PE"}
    assert all(leg.target_points == 10.0 for leg in plan.legs)


def test_trade_plan_strong_bullish_sits_out():
    both_buyer = [
        StrikeQuote(24450, SessionOhlc(high=123.8, close=95.85, low=0), SessionOhlc(high=130.0, close=105.25, low=0)),
    ]
    result = analyze(both_buyer, session_date="2026-07-22", nifty_close=24450)
    assert result.ce.domination == BUYER
    assert result.pe.domination == BUYER

    plan = build_trade_plan(result, trade_date="2026-07-23")
    assert plan.legs == []
    assert "Sitting out" in plan.note


def test_trade_plan_indecision_sits_out():
    indecision = [
        StrikeQuote(24450, SessionOhlc(high=200, close=100, low=0), SessionOhlc(high=200, close=100, low=0)),
    ]
    result = analyze(indecision, session_date="2026-07-23", nifty_close=24450)
    assert result.ce.domination == INDECISION
    assert result.pe.domination == INDECISION

    plan = build_trade_plan(result, trade_date="2026-07-24")
    assert plan.legs == []
    assert "Sitting out" in plan.note


def test_trade_plan_seller_paired_with_indecision_sits_out():
    # Regression: caught live in the real journal -- ce=SELLER + pe=INDECISION
    # was wrongly treated as "Mixed, sell CE" by a bare `elif ce == SELLER`,
    # even though combined_signal() itself calls this exact pairing
    # "Indecision - Sideways Market", not Mixed. The plan must sit out here,
    # matching what the app's own display says the day is.
    ce_seller_pe_indecision = [
        StrikeQuote(
            24450,
            SessionOhlc(high=200, close=95.85, low=90),  # CE: close-low=5.85 -> Seller
            SessionOhlc(high=200, close=100, low=0),  # PE: neither within threshold -> Indecision
        ),
    ]
    result = analyze(ce_seller_pe_indecision, session_date="2026-07-25", nifty_close=24450)
    assert result.ce.domination == SELLER
    assert result.pe.domination == INDECISION
    assert result.combined_signal == "Indecision - Sideways Market"

    plan = build_trade_plan(result, trade_date="2026-07-27")
    assert plan.legs == []
    assert "Sitting out" in plan.note


def test_trade_plan_caps_at_max_trades_per_day():
    both_seller = [
        StrikeQuote(24450, SessionOhlc(high=200, close=95.85, low=90), SessionOhlc(high=200, close=105.25, low=100)),
    ]
    result = analyze(both_seller, session_date="2026-07-21", nifty_close=24450)
    plan = build_trade_plan(result, trade_date="2026-07-22", max_trades_per_day=1)
    assert len(plan.legs) == 1

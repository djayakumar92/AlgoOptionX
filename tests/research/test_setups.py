from datetime import date, datetime, time, timedelta

import pandas as pd

from algooptionx.research.signals import gex, market_structure as ms, regime, setups
from algooptionx.research.signals.oi_walls import OiWall
from algooptionx.research.signals.trend import TrendSummary


def _bars(base: float, count: int = 40, start: datetime | None = None) -> pd.DataFrame:
    start = start or datetime(2026, 9, 4, 9, 15)
    rows = []
    for i in range(count):
        ts = int((start + timedelta(minutes=5 * i)).timestamp())
        price = base + i
        rows.append(
            {"ts": ts, "open": price, "high": price + 5, "low": price - 5, "close": price, "volume": 1000}
        )
    return pd.DataFrame(rows)


def _chain(strike: float = 24000) -> pd.DataFrame:
    rows = []
    for s in (strike - 100, strike, strike + 100):
        rows.append({"strike": s, "option_type": "CE", "ltp": 100.0, "gamma": 0.001, "oi": 100_000, "delta": 0.5})
        rows.append({"strike": s, "option_type": "PE", "ltp": 100.0, "gamma": 0.001, "oi": 100_000, "delta": -0.5})
    return pd.DataFrame(rows)


def _structure(day_type: str, ib_high: float, ib_low: float, session_high: float, session_low: float,
               trend: str = ms.BULLISH) -> ms.MarketStructureSummary:
    return ms.MarketStructureSummary(
        swings=[],
        structure_trend=trend,
        last_bos=None,
        last_choch=None,
        day_type=ms.DayTypeResult(day_type, ib_high, ib_low, session_high, session_low),
        chop=40.0,
        prev_day_high=None,
        prev_day_low=None,
        prev_week_high=None,
        prev_week_low=None,
    )


def _regime(**overrides) -> regime.RegimeSummary:
    defaults = dict(
        as_of="2026-09-04T11:30:00",
        atm_strike=24000.0,
        straddle_price=200.0,
        days_to_expiry=4,
        implied_daily_move_points=100.0,
        realized_daily_move_points=120.0,
        realized_daily_range_points=180.0,
        realized_sample_days=30,
        move_edge_ratio=1.2,
        premium_pricing=regime.CHEAP,
        structure_regime=regime.TRENDING,
        day_type=ms.TREND,
        gamma_regime=gex.NEGATIVE_GAMMA,
        gamma_flip_strike=None,
        iv_percentile=40.0,
        adx=28.0,
        chop=35.0,
        session_window="MIDDAY",
        is_expiry_day=False,
        premium_stance=regime.BUY_FAVORED,
        stance_score=50.0,
        stance_confidence=48.0,
        reasons=[],
        warnings=[],
    )
    defaults.update(overrides)
    return regime.RegimeSummary(**defaults)


def _ctx(**overrides) -> setups.SetupContext:
    defaults = dict(
        spot_price=24010.0,
        chain=_chain(),
        session_candles=_bars(23980),
        structure=_structure(ms.TREND, ib_high=24000, ib_low=23950, session_high=24060, session_low=23945),
        trend=TrendSummary(
            vwap=24000.0, price_vs_vwap="ABOVE", ma_fast=24005.0, ma_slow=23995.0,
            ma_crossover="BULLISH", adx=28.0, trend_strength="STRONG", bias_lean="BULLISH",
        ),
        regime=_regime(),
        gex=None,
        call_walls=[],
        put_walls=[],
        calibration={},
    )
    defaults.update(overrides)
    return setups.SetupContext(**defaults)


def _by_key(signals: list[setups.SetupSignal], key: str) -> setups.SetupSignal:
    return next(s for s in signals if s.key == key)


# ---- gates are hard ------------------------------------------------------


def test_a_failed_gate_blocks_regardless_of_score():
    """The whole point of gates: a perfect-looking setup in the wrong window
    must not be rescued by its evidence score."""
    ctx = _ctx(regime=_regime(session_window="OPENING"))
    signal = _by_key(setups.evaluate(ctx), "IB_BREAKOUT_LONG")
    assert signal.status == setups.BLOCKED
    assert "Market is open and settled" in signal.blocked_by
    assert signal.score > 0  # evidence was still strong; it just cannot fire


def test_blocked_reasons_read_as_the_failure_not_the_requirement():
    """Gate names state the condition that must hold, so listing a failed gate
    by name reads backwards to a human. The reader gets the detail text."""
    ctx = _ctx(regime=_regime(session_window="OPENING"))
    signal = _by_key(setups.evaluate(ctx), "IB_BREAKOUT_LONG")
    assert any("Still inside the first 30 minutes" in r for r in signal.blocked_reasons)


def test_short_straddle_refuses_to_fire_in_a_trend():
    """The domain research's central criticism of the existing rule: it is a
    range-day strategy with nothing checking that it is a range day."""
    ctx = _ctx(regime=_regime(structure_regime=regime.TRENDING))
    signal = _by_key(setups.evaluate(ctx), "RANGE_SHORT_STRADDLE")
    assert signal.status == setups.BLOCKED
    assert "Market is not trending" in signal.blocked_by


def test_short_straddle_arms_in_a_contained_richly_priced_session():
    ctx = _ctx(
        regime=_regime(
            structure_regime=regime.RANGING,
            day_type=ms.NON_TREND,
            premium_pricing=regime.RICH,
            premium_stance=regime.SELL_FAVORED,
            gamma_regime=gex.POSITIVE_GAMMA,
            iv_percentile=75.0,
        ),
        gex=gex.GexSummary([], 5000.0, gex.POSITIVE_GAMMA, 24000.0, 24100.0, 23900.0, 24000.0, ""),
    )
    signal = _by_key(setups.evaluate(ctx), "RANGE_SHORT_STRADDLE")
    assert signal.status == setups.ARMED
    assert signal.score >= 60


def test_expiry_closing_window_shuts_off_every_premium_sale():
    ctx = _ctx(
        regime=_regime(
            structure_regime=regime.RANGING,
            day_type=ms.NON_TREND,
            premium_pricing=regime.RICH,
            is_expiry_day=True,
            session_window="CLOSING",
            gamma_regime=gex.POSITIVE_GAMMA,
        ),
        gex=gex.GexSummary([], 5000.0, gex.POSITIVE_GAMMA, 24000.0, 24100.0, 23900.0, 24000.0, ""),
        call_walls=[OiWall(24100, "CE", 500_000, 60_000, 0.14, 90_000, "FRESH", False)],
    )
    signals = setups.evaluate(ctx)
    for key in ("RANGE_SHORT_STRADDLE", "WALL_FADE_CALL"):
        assert _by_key(signals, key).status == setups.BLOCKED


def test_wall_being_unwound_blocks_the_fade():
    """High volume with falling open interest is the research's specific
    'this wall is about to break' warning -- it must be a gate, not a
    score deduction."""
    ctx = _ctx(
        spot_price=24050.0,
        regime=_regime(structure_regime=regime.RANGING, premium_pricing=regime.RICH),
        call_walls=[OiWall(24100, "CE", 500_000, -80_000, -0.14, 120_000, "STALE", True)],
    )
    signal = _by_key(setups.evaluate(ctx), "WALL_FADE_CALL")
    assert signal.status == setups.BLOCKED
    assert "Wall is not being unwound" in signal.blocked_by


def test_wall_fade_needs_the_wall_on_the_correct_side_of_price():
    ctx = _ctx(
        spot_price=24200.0,  # already above the wall
        regime=_regime(structure_regime=regime.RANGING),
        call_walls=[OiWall(24100, "CE", 500_000, 60_000, 0.14, 90_000, "FRESH", False)],
    )
    signal = _by_key(setups.evaluate(ctx), "WALL_FADE_CALL")
    assert "Wall sits the right side of price" in signal.blocked_by


# ---- both sides of the market are represented ---------------------------


def test_catalog_covers_buying_and_selling():
    signals = setups.evaluate(_ctx())
    sides = {s.side for s in signals}
    assert sides == {setups.BUY_PREMIUM, setups.SELL_PREMIUM}
    actions = {s.action for s in signals}
    assert {"BUY_CE", "BUY_PE", "SELL_CE", "SELL_PE", "SELL_STRADDLE"} <= actions


def test_blocked_setups_are_returned_not_hidden():
    signals = setups.evaluate(_ctx())
    assert any(s.status == setups.BLOCKED for s in signals)
    assert all(s.narrative for s in signals)


# ---- confidence is earned, not asserted ----------------------------------


def test_grade_is_capped_without_history_however_good_the_evidence():
    assert setups._grade(95.0, None) == "C"
    assert setups._grade(95.0, setups.CalibrationRead(3, 3, 100.0, 20.0, "")) == "C"
    assert setups._grade(95.0, setups.CalibrationRead(8, 5, 62.5, 15.0, "")) == "B"
    assert setups._grade(95.0, setups.CalibrationRead(30, 20, 66.7, 18.0, "")) == "A"


def test_every_signal_without_history_says_so():
    for signal in setups.evaluate(_ctx()):
        assert any("never been graded" in w for w in signal.warnings)


def test_calibration_is_attached_when_present():
    read = setups.CalibrationRead(25, 16, 64.0, 22.0, "note")
    ctx = _ctx(calibration={"IB_BREAKOUT_LONG": read})
    signal = _by_key(setups.evaluate(ctx), "IB_BREAKOUT_LONG")
    assert signal.historical is read
    assert not any("never been graded" in w for w in signal.warnings)


# ---- every signal is actionable and falsifiable -------------------------


def test_every_signal_states_assumption_trigger_and_invalidation():
    for signal in setups.evaluate(_ctx()):
        assert signal.assumption and len(signal.assumption) > 40
        assert signal.trigger
        assert signal.invalidation


def test_evidence_weights_sum_to_one_hundred_per_setup():
    for signal in setups.evaluate(_ctx()):
        assert sum(e.weight for e in signal.evidence) == 100


def test_score_reflects_only_earned_evidence():
    signal = _by_key(setups.evaluate(_ctx()), "IB_BREAKOUT_LONG")
    earned = sum(e.earned for e in signal.evidence)
    assert signal.score == round(earned, 1)


def test_expected_premium_uses_delta_and_stays_conservative():
    signal = _by_key(setups.evaluate(_ctx()), "IB_BREAKOUT_LONG")
    # 0.5 delta on a 60-point underlying target -> ~30 premium points
    assert signal.expected_premium_points is not None
    assert signal.expected_premium_points < abs(signal.target_reference - signal.entry_reference)


# ---- best_setup ----------------------------------------------------------


def test_best_setup_returns_none_when_nothing_qualifies():
    ctx = _ctx(regime=_regime(session_window="OPENING"), structure=None, trend=None, gex=None)
    assert setups.best_setup(setups.evaluate(ctx)) is None


def test_best_setup_prefers_an_armed_signal_over_a_higher_scoring_blocked_one():
    ctx = _ctx(
        regime=_regime(
            structure_regime=regime.RANGING,
            day_type=ms.NON_TREND,
            premium_pricing=regime.RICH,
            premium_stance=regime.SELL_FAVORED,
            gamma_regime=gex.POSITIVE_GAMMA,
        ),
        gex=gex.GexSummary([], 5000.0, gex.POSITIVE_GAMMA, 24000.0, 24100.0, 23900.0, 24000.0, ""),
    )
    best = setups.best_setup(setups.evaluate(ctx))
    assert best is not None and best.status == setups.ARMED


def test_setups_degrade_rather_than_crash_without_structure_or_chain():
    ctx = _ctx(structure=None, trend=None, gex=None, chain=pd.DataFrame(columns=["strike", "option_type", "ltp"]))
    signals = setups.evaluate(ctx)
    assert isinstance(signals, list)  # only the setups that can be built are returned


def test_nothing_arms_while_the_market_is_closed():
    """Opening the app before the bell used to classify as OPENING, which the
    gates let through for every setup that only excluded the closing window.
    A read of yesterday is fine; offering a trade on it is not."""
    ctx = _ctx(
        regime=_regime(
            session_window="CLOSED",
            structure_regime=regime.RANGING,
            day_type=ms.NON_TREND,
            premium_pricing=regime.RICH,
            premium_stance=regime.SELL_FAVORED,
            gamma_regime=gex.POSITIVE_GAMMA,
            is_expiry_day=True,
        ),
        gex=gex.GexSummary([], 5000.0, gex.POSITIVE_GAMMA, 24000.0, 24100.0, 23900.0, 24000.0, ""),
        call_walls=[OiWall(24100, "CE", 500_000, 60_000, 0.14, 90_000, "FRESH", False)],
        put_walls=[OiWall(23900, "PE", 500_000, 60_000, 0.14, 90_000, "FRESH", False)],
    )
    signals = setups.evaluate(ctx)
    assert all(s.status == setups.BLOCKED for s in signals)
    assert setups.best_setup(signals) is None

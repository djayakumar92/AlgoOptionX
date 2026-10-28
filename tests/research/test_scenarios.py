"""The scenario engine, and specifically the promise that its percentages are
evidence shares rather than invented probabilities."""

from datetime import datetime

import pytest

from algooptionx.research.signals import gex, market_structure as ms, regime, scenarios, setups
from algooptionx.research.signals.oi_walls import OiWall
from algooptionx.research.signals.risk import assess_risk
from algooptionx.research.signals.trend import TrendSummary


class _Level:
    """Stands in for api.prediction.KeyLevel -- scenarios only reads price/kind."""

    def __init__(self, price: float, kind: str):
        self.price = price
        self.kind = kind


def _regime(**overrides) -> regime.RegimeSummary:
    defaults = dict(
        as_of="2026-09-08T12:00:00", atm_strike=24000.0, straddle_price=200.0, days_to_expiry=3,
        implied_daily_move_points=100.0, realized_daily_move_points=120.0,
        realized_daily_range_points=180.0, realized_sample_days=30, move_edge_ratio=1.2,
        premium_pricing=regime.CHEAP, structure_regime=regime.TRENDING, day_type=ms.TREND,
        gamma_regime=gex.NEGATIVE_GAMMA, gamma_flip_strike=None, iv_percentile=40.0,
        adx=28.0, chop=35.0, session_window="MIDDAY", is_expiry_day=False,
        premium_stance=regime.BUY_FAVORED, stance_score=50.0, stance_confidence=48.0,
        reasons=[], warnings=[],
    )
    defaults.update(overrides)
    return regime.RegimeSummary(**defaults)


def _structure(trend: str, timeframes: list[str] | None = None) -> ms.MarketStructureSummary:
    tfs = [
        ms.TimeframeStructure(label, t, 200, 20, True, "")
        for label, t in zip(("1D", "1H", "15M"), timeframes or [trend] * 3)
    ]
    return ms.MarketStructureSummary(
        swings=[], structure_trend=trend, last_bos=None, last_choch=None,
        day_type=ms.DayTypeResult(ms.TREND, 24000, 23950, 24060, 23945), chop=40.0,
        prev_day_high=None, prev_day_low=None, prev_week_high=None, prev_week_low=None,
        timeframes=tfs,
    )


def _levels() -> list[_Level]:
    return [_Level(24100, "RESISTANCE"), _Level(24050, "RESISTANCE"),
            _Level(23950, "SUPPORT"), _Level(23900, "SUPPORT")]


def _signal(readiness: str) -> setups.SetupSignal:
    return setups.SetupSignal(
        key="IB_BREAKOUT_LONG", name="Opening-range breakout (up)", action="BUY_CE",
        side=setups.BUY_PREMIUM, direction="BULLISH", status=setups.ARMED, gates=[],
        blocked_by=[], blocked_reasons=[], evidence=[], score=80.0, grade="B",
        assumption="", trigger="", invalidation="", strike=24000.0, entry_reference=24050.0,
        stop_reference=24050.0, target_reference=24110.0, expected_premium_points=30.0,
        readiness=readiness, distance_points=5.0, readiness_note="", historical=None,
    )


def _build(**overrides):
    kwargs = dict(
        spot_price=24000.0,
        summary=_regime(),
        structure=_structure(ms.BULLISH),
        trend=TrendSummary(24000.0, "ABOVE", 24005.0, 23995.0, "BULLISH", 28.0, "STRONG", "BULLISH"),
        gex_summary=None,
        signals=[],
        key_levels=_levels(),
        call_walls=[],
        put_walls=[],
        risk_assessment=assess_risk(datetime(2026, 9, 8, 12, 0), False),
    )
    kwargs.update(overrides)
    return scenarios.build(**kwargs)


# ---- the three scenarios -------------------------------------------------


def test_always_exactly_three_scenarios():
    """Price can take out the level above, the level below, or neither. There
    is no fourth thing, so the page never has to invent one."""
    result = _build()
    assert {s.key for s in result.scenarios} == {"UPSIDE", "RANGE", "DOWNSIDE"}


def test_shares_total_one_hundred_and_are_labelled_as_evidence():
    result = _build()
    assert sum(s.evidence_share for s in result.scenarios) == pytest.approx(100.0, abs=0.5)
    assert "not a probability" in result.caveat


def test_unreadable_factors_are_excluded_rather_than_counted_as_range():
    """A factor that cannot be read must not quietly become evidence for the
    do-nothing scenario -- that would manufacture support out of ignorance."""
    blind = _build(
        summary=_regime(premium_pricing=regime.PRICING_UNKNOWN, day_type=ms.INSUFFICIENT_DATA),
        structure=ms.MarketStructureSummary(
            swings=[], structure_trend=ms.BULLISH, last_bos=None, last_choch=None,
            day_type=ms.DayTypeResult(ms.INSUFFICIENT_DATA, None, None, None, None), chop=None,
            prev_day_high=None, prev_day_low=None, prev_week_high=None, prev_week_low=None,
            timeframes=[],
        ),
        gex_summary=None,
    )
    range_case = next(s for s in blind.scenarios if s.key == "RANGE")
    unreadable = {"Dealer gamma", "Option pricing", "Day type", "Higher timeframes"}
    assert not (unreadable & {e.factor for e in range_case.evidence})
    assert sum(s.evidence_share for s in blind.scenarios) == pytest.approx(100.0, abs=0.5)


def test_bullish_evidence_lands_on_the_upside_scenario():
    result = _build()
    upside = next(s for s in result.scenarios if s.key == "UPSIDE")
    downside = next(s for s in result.scenarios if s.key == "DOWNSIDE")
    assert upside.evidence_share > downside.evidence_share
    assert "Swing structure" in {e.factor for e in upside.evidence}


def test_damped_choppy_conditions_favour_the_range():
    result = _build(
        summary=_regime(day_type=ms.NON_TREND, premium_pricing=regime.RICH,
                        gamma_regime=gex.POSITIVE_GAMMA, adx=15.0),
        structure=_structure(ms.UNCLEAR),
        trend=TrendSummary(24000.0, "AT", 24000.0, 24000.0, "NONE", 15.0, "WEAK", "NEUTRAL"),
        gex_summary=gex.GexSummary([], 500.0, gex.POSITIVE_GAMMA, 24000.0, 24100.0, 23900.0,
                                   24000.0, ""),
    )
    assert result.scenarios[0].key == "RANGE"


def test_triggers_use_the_nearest_real_levels():
    result = _build()
    upside = next(s for s in result.scenarios if s.key == "UPSIDE")
    downside = next(s for s in result.scenarios if s.key == "DOWNSIDE")
    assert upside.trigger_level == 24050  # nearest resistance above 24,000
    assert downside.trigger_level == 23950  # nearest support below
    assert all(s.trigger and s.invalidation for s in result.scenarios)


def test_scenarios_are_ordered_by_evidence():
    shares = [s.evidence_share for s in _build().scenarios]
    assert shares == sorted(shares, reverse=True)


# ---- the checklist -------------------------------------------------------


def test_checklist_conditions_are_all_real_and_can_fail():
    """The mocked version hardcoded eight ticks and two crosses."""
    result = _build()
    assert result.checklist_total == 10
    assert all(item.detail for item in result.checklist)

    starved = _build(
        summary=_regime(session_window="CLOSED", premium_pricing=regime.PRICING_UNKNOWN,
                        straddle_price=None),
        structure=None,
        gex_summary=None,
        key_levels=[],
        risk_assessment=assess_risk(datetime(2026, 9, 8, 6, 0), False),
    )
    assert starved.checklist_passed < result.checklist_passed


def test_closed_market_stands_down_however_good_the_evidence():
    result = _build(summary=_regime(session_window="CLOSED"))
    assert result.verdict == scenarios.STAND_DOWN
    assert "closed" in result.verdict_note.lower()


def test_an_armed_setup_at_its_level_reads_as_trade():
    signal = _signal(setups.NOW)
    result = _build(signals=[signal])
    assert result.verdict == scenarios.TRADE
    upside = next(s for s in result.scenarios if s.key == "UPSIDE")
    assert signal.name in upside.matching_setups


def test_armed_but_far_from_the_level_reads_as_wait():
    assert _build(signals=[_signal(setups.WAIT)]).verdict == scenarios.WAIT


def test_no_armed_setup_stands_down():
    assert _build(signals=[]).verdict == scenarios.STAND_DOWN


def test_fresh_walls_satisfy_the_open_interest_condition():
    fresh = OiWall(24100, "CE", 500_000, 60_000, 0.14, 90_000, "FRESH", False)
    stale = OiWall(24100, "CE", 500_000, 1_000, 0.002, 5_000, "STALE", False)
    name = "Open interest shows fresh conviction"
    assert next(i for i in _build(call_walls=[fresh]).checklist if i.name == name).passed
    assert not next(i for i in _build(call_walls=[stale]).checklist if i.name == name).passed

from datetime import date, datetime, time, timedelta

import pandas as pd
import pytest

from dhan_analyzer.signals import gex, market_structure as ms, regime


def sessions(prices: list[tuple[float, float, float, float]], start: date, step_days: int = 1) -> pd.DataFrame:
    """Daily OHLC rows on consecutive (or step_days-apart) dates."""
    rows = []
    day = start
    for o, h, low, c in prices:
        rows.append(
            {
                "ts": int(datetime.combine(day, time(0, 0)).timestamp()),
                "open": o,
                "high": h,
                "low": low,
                "close": c,
            }
        )
        day = day + timedelta(days=step_days)
    return pd.DataFrame(rows)


def intraday(bars: list[tuple[datetime, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ts": int(ts.timestamp()), "open": o, "high": h, "low": low, "close": c}
            for ts, o, h, low, c in bars
        ]
    )


# ---- expiry weekday ------------------------------------------------------


def test_expiry_weekday_fallback_is_tuesday_not_thursday():
    # 2026-09-08 is a Tuesday; 2026-09-10 is a Thursday.
    assert regime.is_expiry_day(date(2026, 9, 8)) is True
    assert regime.is_expiry_day(date(2026, 9, 10)) is False


def test_tracked_expiry_overrides_the_weekday_rule():
    """A holiday-shifted expiry must win over the weekday heuristic."""
    holiday_shifted = date(2026, 9, 9)  # a Wednesday
    assert regime.is_expiry_day(date(2026, 9, 9), holiday_shifted) is True
    assert regime.is_expiry_day(date(2026, 9, 8), holiday_shifted) is False


# ---- movement measurement -----------------------------------------------


def test_realized_move_measures_displacement_not_range():
    """A market that swings 200 points intraday but closes flat has moved
    nothing in the sense a straddle pays on -- the two measures must differ."""
    frame = sessions(
        [(24000, 24100, 23900, 24000)] * 6,
        start=date(2026, 8, 3),
    )
    move, _ = regime.realized_daily_move(frame)
    rng, _ = regime.realized_daily_range(frame)
    assert move == pytest.approx(0.0, abs=0.01)
    assert rng > 100


def test_gap_in_stored_history_is_not_counted_as_one_session_move():
    """Two sessions five weeks apart are a hole in the data, not an overnight
    move -- counting it inflated realized movement to twice its real value the
    first time this ran on live data."""
    contiguous = sessions(
        [(24000, 24050, 23950, 24010), (24010, 24060, 23960, 24020)],
        start=date(2026, 8, 3),
    )
    with_hole = pd.concat(
        [contiguous, sessions([(23000, 23100, 22900, 23000)], start=date(2026, 9, 21))],
        ignore_index=True,
    )
    clean, _ = regime.realized_daily_move(contiguous)
    holed, _ = regime.realized_daily_move(with_hole)
    assert holed == pytest.approx(clean, abs=0.01)


def test_intraday_bars_are_folded_into_sessions():
    bars = intraday(
        [
            (datetime(2026, 9, 1, 9, 15), 24000, 24020, 23990, 24010),
            (datetime(2026, 9, 1, 9, 20), 24010, 24080, 24005, 24070),
            (datetime(2026, 9, 2, 9, 15), 24070, 24090, 24000, 24020),
        ]
    )
    daily = regime.daily_from_intraday(bars)
    assert len(daily) == 2
    first = daily.iloc[0]
    assert first["open"] == 24000 and first["high"] == 24080
    assert first["low"] == 23990 and first["close"] == 24070


def test_intraday_source_is_preferred_over_shorter_daily_history():
    stale_daily = sessions([(24000, 24100, 23900, 24000)] * 2, start=date(2026, 5, 11))
    bars = intraday(
        [
            (datetime(2026, 9, d, 9, 15), 24000, 24000 + 50 * d, 23990, 24000 + 40 * d)
            for d in range(1, 6)
        ]
    )
    _, sample = regime.realized_daily_move(stale_daily, intraday_candles=bars)
    assert sample >= 4  # came from the five rebuilt sessions, not the two stale ones


# ---- implied move --------------------------------------------------------


def test_implied_daily_move_scales_by_square_root_of_time():
    assert regime.implied_daily_move(200.0, 4) == pytest.approx(100.0)
    assert regime.implied_daily_move(200.0, 1) == pytest.approx(200.0)


def test_implied_daily_move_is_none_without_a_straddle():
    assert regime.implied_daily_move(None, 3) is None
    assert regime.implied_daily_move(150.0, None) is None


def test_atm_straddle_picks_nearest_strike_to_spot():
    chain = pd.DataFrame(
        [
            {"strike": 23900, "option_type": "CE", "ltp": 120.0},
            {"strike": 23900, "option_type": "PE", "ltp": 80.0},
            {"strike": 24000, "option_type": "CE", "ltp": 60.0},
            {"strike": 24000, "option_type": "PE", "ltp": 140.0},
        ]
    )
    strike, straddle = regime.atm_straddle(chain, spot_price=23920)
    assert strike == 23900
    assert straddle == pytest.approx(200.0)


# ---- structure regime ----------------------------------------------------


def test_day_type_can_outvote_a_single_indicator():
    assert regime.classify_structure_regime(adx=30, chop=None, day_type=ms.NON_TREND) == regime.RANGING
    assert regime.classify_structure_regime(adx=15, chop=None, day_type=ms.TREND) == regime.TRENDING


def test_regime_is_unknown_when_nothing_is_readable():
    assert (
        regime.classify_structure_regime(adx=None, chop=None, day_type=ms.INSUFFICIENT_DATA)
        == regime.REGIME_UNKNOWN
    )


# ---- the stance ----------------------------------------------------------


def _chain(ce: float, pe: float, strike: float = 24000) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"strike": strike, "option_type": "CE", "ltp": ce, "gamma": 0.001, "oi": 100_000, "delta": 0.5},
            {"strike": strike, "option_type": "PE", "ltp": pe, "gamma": 0.001, "oi": 100_000, "delta": -0.5},
        ]
    )


def _quiet_daily() -> pd.DataFrame:
    """Sessions that barely move -- realized displacement near zero."""
    return sessions([(24000, 24020, 23980, 24000)] * 25, start=date(2026, 7, 1))


def test_rich_premium_and_contained_day_produce_a_sell_stance():
    summary = regime.summarize(
        spot_price=24000,
        chain=_chain(ce=150, pe=150),  # 300-point straddle against a market going nowhere
        daily_candles=_quiet_daily(),
        structure=None,
        gex_summary=None,
        tracked_expiry=date(2026, 9, 8),
        now=datetime(2026, 9, 4, 11, 30),
    )
    assert summary.premium_pricing == regime.RICH
    assert summary.premium_stance == regime.SELL_FAVORED
    assert any(r.points < 0 for r in summary.reasons)


def test_every_factor_is_reported_even_when_it_contributes_nothing():
    summary = regime.summarize(
        spot_price=24000,
        chain=_chain(ce=150, pe=150),
        daily_candles=_quiet_daily(),
        structure=None,
        gex_summary=None,
        tracked_expiry=date(2026, 9, 8),
        now=datetime(2026, 9, 4, 11, 30),
    )
    factors = {r.factor for r in summary.reasons}
    assert "Market structure" in factors
    assert "Dealer gamma" in factors
    assert "Implied volatility level" in factors
    # every reason carries an explanation the UI can render verbatim
    assert all(r.explanation for r in summary.reasons)


def test_thin_history_halves_the_pricing_weight_and_warns():
    short = sessions([(24000, 24020, 23980, 24000)] * 4, start=date(2026, 9, 1))
    summary = regime.summarize(
        spot_price=24000,
        chain=_chain(ce=150, pe=150),
        daily_candles=short,
        structure=None,
        gex_summary=None,
        tracked_expiry=date(2026, 9, 8),
        now=datetime(2026, 9, 4, 11, 30),
    )
    pricing = next(r for r in summary.reasons if r.factor.startswith("Premium pricing"))
    assert abs(pricing.points) == regime._W_VRP / 2
    assert any("days of history" in w for w in summary.warnings)


def test_expiry_day_warns_about_gamma():
    summary = regime.summarize(
        spot_price=24000,
        chain=_chain(ce=40, pe=40),
        daily_candles=_quiet_daily(),
        structure=None,
        gex_summary=None,
        tracked_expiry=date(2026, 9, 8),
        now=datetime(2026, 9, 8, 11, 30),
    )
    assert summary.is_expiry_day is True
    assert any("gamma" in w.lower() or "sensitivity" in w.lower() for w in summary.warnings)


def test_opening_window_warns_against_new_positions():
    summary = regime.summarize(
        spot_price=24000,
        chain=_chain(ce=100, pe=100),
        daily_candles=_quiet_daily(),
        structure=None,
        gex_summary=None,
        tracked_expiry=date(2026, 9, 8),
        now=datetime(2026, 9, 4, 9, 25),
        session_window="OPENING",
    )
    assert any("First 30 minutes" in w for w in summary.warnings)


def test_missing_pricing_inputs_warn_rather_than_silently_neutralise():
    summary = regime.summarize(
        spot_price=24000,
        chain=pd.DataFrame(columns=["strike", "option_type", "ltp"]),
        daily_candles=pd.DataFrame(columns=["high", "low", "close"]),
        structure=None,
        gex_summary=None,
        tracked_expiry=date(2026, 9, 8),
        now=datetime(2026, 9, 4, 11, 30),
    )
    assert summary.premium_pricing == regime.PRICING_UNKNOWN
    assert any("priced movement" in w for w in summary.warnings)


def test_iv_percentile_needs_a_real_sample():
    assert regime.iv_percentile(15.0, [10.0] * 5) is None
    assert regime.iv_percentile(15.0, [10.0] * 25) == 100.0


def test_trading_days_to_expiry_excludes_weekends():
    # Fri 2026-09-04 to Tue 2026-09-08 is Fri, Mon, Tue = 3 sessions.
    assert regime.trading_days_to_expiry(date(2026, 9, 4), date(2026, 9, 8)) == 3
    assert regime.trading_days_to_expiry(date(2026, 9, 8), date(2026, 9, 8)) == 1

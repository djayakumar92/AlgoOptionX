from datetime import datetime, timedelta

import pandas as pd

from dhan_analyzer.signals import ledger


def bars(prices: list[tuple[float, float, float]], start: datetime | None = None) -> pd.DataFrame:
    """(high, low, close) per 5-minute bar, opening at the previous close."""
    start = start or datetime(2026, 9, 4, 9, 15)
    rows = []
    for i, (high, low, close) in enumerate(prices):
        rows.append(
            {
                "ts": int((start + timedelta(minutes=5 * i)).timestamp()),
                "open": close,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows)


ARM_TS = int(datetime(2026, 9, 4, 9, 15).timestamp())


def buy_event(**overrides) -> dict:
    event = {
        "id": 1,
        "trade_date": "2026-09-04",
        "setup_key": "IB_BREAKOUT_LONG",
        "armed_ts": ARM_TS,
        "spot_at_arm": 24000.0,
        "action": "BUY_CE",
        "side": "BUY_PREMIUM",
        "direction": "BULLISH",
        "entry_reference": 24000.0,
        "stop_reference": 24000.0,
        "target_reference": 24080.0,
        "expected_move_points": 100.0,
    }
    event.update(overrides)
    return event


# ---- bought-premium grading ---------------------------------------------


def test_never_triggered_is_its_own_result_not_a_loss():
    """A setup that armed and never triggered cost nothing and proves nothing.
    Counting it as a loss would understate the rule; as a win, flatter it."""
    candles = bars([(23990, 23950, 23960)] * 10)
    graded = ledger.grade_event(buy_event(), candles)
    assert graded.result == ledger.NOT_TRIGGERED
    assert graded.triggered is False
    assert graded.underlying_points is None


def test_target_reached_before_invalidation_is_a_win():
    candles = bars(
        [(24010, 23995, 24005)] + [(24040, 24000, 24035)] + [(24090, 24050, 24085)] * 3
    )
    graded = ledger.grade_event(buy_event(), candles)
    assert graded.result == ledger.WIN
    assert graded.hit_target is True
    assert graded.underlying_points > 0


def test_invalidation_before_target_is_a_loss():
    candles = bars([(24010, 23995, 24005), (24006, 23950, 23960), (24100, 23960, 24090)])
    graded = ledger.grade_event(buy_event(), candles)
    assert graded.result == ledger.LOSS
    assert graded.hit_invalidation is True
    assert graded.underlying_points < 0


def test_drift_without_either_level_is_flat():
    candles = bars([(24010, 23995, 24005)] + [(24012, 24001, 24006)] * 5)
    graded = ledger.grade_event(buy_event(), candles)
    assert graded.result == ledger.FLAT
    assert graded.hit_target is False and graded.hit_invalidation is False


def test_bearish_setup_triggers_on_a_close_below_the_level():
    event = buy_event(
        action="BUY_PE", direction="BEARISH", entry_reference=24000.0,
        stop_reference=24000.0, target_reference=23920.0,
    )
    candles = bars([(24005, 23985, 23990), (23990, 23910, 23915)])
    graded = ledger.grade_event(event, candles)
    assert graded.triggered is True
    assert graded.result == ledger.WIN


def test_excursions_are_recorded_for_both_directions():
    candles = bars([(24010, 23995, 24005), (24070, 23970, 24060)])
    graded = ledger.grade_event(buy_event(), candles)
    assert graded.mfe_points > 0
    assert graded.mae_points > 0


def test_bars_before_the_arm_time_are_ignored():
    """A setup cannot be credited with a move that happened before it armed."""
    early = bars([(24100, 24050, 24090)], start=datetime(2026, 9, 4, 9, 0))
    later = bars([(23990, 23950, 23960)] * 5, start=datetime(2026, 9, 4, 9, 15))
    graded = ledger.grade_event(buy_event(), pd.concat([early, later], ignore_index=True))
    assert graded.result == ledger.NOT_TRIGGERED


# ---- sold-premium grading -----------------------------------------------


def sell_event(**overrides) -> dict:
    event = {
        "id": 2,
        "trade_date": "2026-09-04",
        "setup_key": "WALL_FADE_CALL",
        "armed_ts": ARM_TS,
        "spot_at_arm": 24000.0,
        "action": "SELL_CE",
        "side": "SELL_PREMIUM",
        "direction": "BEARISH",
        "entry_reference": 24100.0,
        "stop_reference": 24100.0,
        "target_reference": None,
        "expected_move_points": 100.0,
    }
    event.update(overrides)
    return event


def test_sold_call_level_holding_is_a_win():
    candles = bars([(24090, 24000, 24050)] * 6)
    graded = ledger.grade_event(sell_event(), candles)
    assert graded.result == ledger.WIN
    assert graded.hit_invalidation is False
    assert "grades the level, not the option's profit" in graded.note


def test_sold_call_level_breaking_is_a_loss():
    candles = bars([(24090, 24000, 24050), (24160, 24080, 24150)])
    graded = ledger.grade_event(sell_event(), candles)
    assert graded.result == ledger.LOSS
    assert graded.hit_invalidation is True


def test_sold_put_level_uses_the_opposite_direction():
    event = sell_event(action="SELL_PE", direction="BULLISH", stop_reference=23900.0)
    holds = bars([(24000, 23920, 23960)] * 4)
    breaks = bars([(24000, 23920, 23960), (23930, 23850, 23860)])
    assert ledger.grade_event(event, holds).result == ledger.WIN
    assert ledger.grade_event(event, breaks).result == ledger.LOSS


def test_a_wick_through_the_level_is_not_a_break():
    """The invalidation each setup states is a 5-minute *close* through the
    level, so grading must use closes too -- otherwise the record punishes
    the rule for something the rule never said."""
    candles = bars([(24150, 24000, 24050)] * 4)  # high pokes above, closes stay under
    graded = ledger.grade_event(sell_event(), candles)
    assert graded.result == ledger.WIN
    assert graded.mae_points > 0  # the poke is still recorded as adverse excursion


# ---- straddle grading ----------------------------------------------------


def straddle_event(**overrides) -> dict:
    event = {
        "id": 3,
        "trade_date": "2026-09-04",
        "setup_key": "RANGE_SHORT_STRADDLE",
        "armed_ts": ARM_TS,
        "spot_at_arm": 24000.0,
        "action": "SELL_STRADDLE",
        "side": "SELL_PREMIUM",
        "direction": "NEUTRAL",
        "entry_reference": 24000.0,
        "stop_reference": None,
        "target_reference": None,
        "expected_move_points": 100.0,
    }
    event.update(overrides)
    return event


def test_straddle_is_graded_on_where_the_session_finished():
    """It pays out on the final distance from the anchor, not on how far the
    session wandered getting there."""
    candles = bars([(24180, 23990, 24170), (24170, 23980, 24020)])
    graded = ledger.grade_event(straddle_event(), candles)
    assert graded.result == ledger.WIN  # finished 20 points away, inside the 100-point band


def test_a_round_trip_through_the_band_is_still_recorded_as_adverse():
    candles = bars([(24180, 23990, 24170), (24170, 23980, 24020)])
    graded = ledger.grade_event(straddle_event(), candles)
    assert graded.mae_points >= 180 - 100
    assert "would have breached the band" in graded.note


def test_finishing_outside_the_band_is_a_loss():
    candles = bars([(24160, 24000, 24150)] * 3)
    graded = ledger.grade_event(straddle_event(), candles)
    assert graded.result == ledger.LOSS


def test_straddle_without_a_recorded_band_is_not_graded():
    graded = ledger.grade_event(straddle_event(expected_move_points=None), bars([(24010, 23990, 24000)]))
    assert graded.result == ledger.NOT_TRIGGERED


# ---- row builders --------------------------------------------------------


def test_daily_outcome_row_reports_gap_range_and_net():
    candles = bars([(24050, 23980, 24000), (24120, 24010, 24100)])
    row = ledger.daily_outcome_row("2026-09-04", candles, prev_close=23950.0)
    assert row["gap_points"] == 50.0  # open 24000 against a 23950 previous close
    assert row["range_points"] == 140.0  # 24120 - 23980
    assert row["net_points"] == 100.0  # 24100 - 24000


def test_daily_outcome_row_is_none_without_candles():
    assert ledger.daily_outcome_row("2026-09-04", pd.DataFrame(), prev_close=1.0) is None


def test_outcome_row_carries_the_event_identity():
    graded = ledger.grade_event(buy_event(), bars([(23990, 23950, 23960)]))
    row = ledger.outcome_row(buy_event(), graded)
    assert row["event_id"] == 1
    assert row["setup_key"] == "IB_BREAKOUT_LONG"
    assert row["triggered"] == 0


def test_a_broken_sell_level_reports_a_negative_result():
    """A 0% hit rate sitting next to a positive average points figure is
    nonsense -- the loss is how far the breaking candle closed past the
    level, not the cushion left at the end of the day."""
    candles = bars([(24160, 24080, 24150), (24140, 24000, 24010)])
    graded = ledger.grade_event(sell_event(), candles)
    assert graded.result == ledger.LOSS
    assert graded.underlying_points < 0

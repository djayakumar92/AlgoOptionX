from dhan_analyzer.signals.journal_grading import (
    NOT_TRIGGERED,
    OPEN_AT_CLOSE,
    STOP_HIT,
    TARGET_HIT,
    grade_leg,
)


def _candle(high, low, close):
    return {"high": high, "low": low, "close": close}


def test_never_triggers_if_price_never_reaches_entry():
    candles = [_candle(90, 80, 85), _candle(92, 84, 88), _candle(89, 82, 86)]
    result = grade_leg(candles, entry_trigger=100.0, target=80.0)
    assert result.outcome == NOT_TRIGGERED
    assert result.realized_points is None


def test_triggers_then_hits_target():
    candles = [
        _candle(101, 95, 100),  # entry candle: high reaches 100 trigger
        _candle(100, 90, 92),  # stop level = 101 (prev high), low 90 <= target 85? no
        _candle(99, 84, 86),  # low 84 <= target 85 -> target hit
    ]
    result = grade_leg(candles, entry_trigger=100.0, target=85.0)
    assert result.outcome == TARGET_HIT
    assert result.realized_points == 15.0


def test_triggers_then_hits_stop():
    candles = [
        _candle(101, 95, 100),  # entry candle, high=101
        _candle(103, 96, 102),  # stop level = prev high 101, this candle's high 103 >= 101 -> stop hit
    ]
    result = grade_leg(candles, entry_trigger=100.0, target=80.0)
    assert result.outcome == STOP_HIT
    assert result.realized_points == -1.0  # entry_trigger(100) - stop_level(101)


def test_triggers_but_neither_hit_by_session_end():
    candles = [
        _candle(101, 95, 100),
        _candle(100, 97, 98),
    ]
    result = grade_leg(candles, entry_trigger=100.0, target=50.0)
    assert result.outcome == OPEN_AT_CLOSE
    assert result.realized_points == 2.0  # entry_trigger(100) - last_close(98)

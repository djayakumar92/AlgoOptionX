from datetime import date, datetime

import pandas as pd

from dhan_analyzer.signals import market_structure
from dhan_analyzer.signals.market_structure import (
    BEARISH,
    BOS,
    BULLISH,
    CHOCH,
    FORMING,
    HH,
    HIGH,
    HL,
    LH,
    LL,
    LOW,
    NEUTRAL,
    NON_TREND,
    NORMAL_VARIATION,
    TREND,
    UNCLEAR,
    SwingPoint,
    classify_day_type,
    classify_structure,
    find_swings,
    previous_day_close,
    previous_day_high_low,
    previous_week_high_low,
)

DAY_SECONDS = 86400


def _candles(closes: list[float], ts0: int = 1_000_000, step: int = 300, spread: float = 0.3) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": [ts0 + i * step for i in range(len(closes))],
            "high": [c + spread for c in closes],
            "low": [c - spread for c in closes],
            "close": closes,
        }
    )


# ---- find_swings ----------------------------------------------------------

def test_find_swings_detects_a_clear_fractal_high():
    closes = [100, 101, 102, 108, 102, 101.4, 101, 100.3, 100, 99, 98]
    candles = _candles(closes)
    swings = find_swings(candles, n=2, atr_mult=0.1)
    highs = [s for s in swings if s.kind == HIGH]
    assert len(highs) == 1
    assert highs[0].price == 108.3
    assert highs[0].label == "H"  # first high seen -- nothing to compare yet


def test_find_swings_same_kind_replacement_keeps_more_extreme():
    # Two fractal highs (idx2, idx6) with a shallow wiggle between them that
    # -- by construction (idx1 is lower than the wiggle, so it fails the
    # fractal test on its own) -- never forms a competing low swing. With no
    # opposite-kind swing in between, the later/higher peak should replace
    # the earlier one rather than both being kept as consecutive same-kind
    # confirmed swings (which zigzag structure never allows).
    closes = [100, 101, 105, 103, 104, 103, 130, 101, 100, 101, 102, 90, 92, 94, 96, 99]
    candles = _candles(closes)
    swings = find_swings(candles, n=2, atr_mult=20.0)
    highs = [s for s in swings if s.kind == HIGH]
    assert len(highs) == 1
    assert highs[0].price == 130.3


def test_find_swings_rejects_move_smaller_than_atr_filter():
    # A small retracement (~1.7 pts) after a big rally, with atr_mult set high
    # enough that this specific move can't clear the filter regardless of the
    # exact ATR value -- the confirmed low should be the deeper one further on.
    closes = [100, 101, 108, 106.3, 107, 108, 109, 90, 91, 92, 93, 95]
    candles = _candles(closes)
    swings = find_swings(candles, n=2, atr_mult=5.0)
    kinds_labels = [(s.kind, round(s.price, 1)) for s in swings]
    # The shallow dip at index 3 (106.3) must not appear as a confirmed low;
    # only the real swing high and the deep swing low should survive.
    assert (LOW, 106.0) not in kinds_labels
    assert any(k == HIGH for k, _ in kinds_labels)


def test_find_swings_too_short_series_returns_empty():
    candles = _candles([100, 101, 102])
    assert find_swings(candles, n=3) == []


# ---- classify_structure ----------------------------------------------------

def _swing(ts, price, kind, label):
    return SwingPoint(ts=ts, price=price, kind=kind, label=label)


def test_classify_structure_establishes_bullish_trend_from_hh_hl():
    swings = [
        _swing(1, 100, LOW, "L"),
        _swing(2, 110, HIGH, "H"),
        _swing(3, 105, LOW, HL),  # higher low -- but trend not yet BULLISH until a HH confirms it
        _swing(4, 115, HIGH, HH),  # higher high -- establishes BULLISH, and is itself the first HH (no BOS yet, trend was UNCLEAR)
    ]
    trend, last_bos, last_choch = classify_structure(swings)
    assert trend == BULLISH
    assert last_choch is None


def test_classify_structure_bos_on_continuation():
    swings = [
        _swing(1, 100, LOW, "L"),
        _swing(2, 110, HIGH, "H"),
        _swing(3, 105, LOW, HL),
        _swing(4, 115, HIGH, HH),  # trend -> BULLISH
        _swing(5, 108, LOW, HL),
        _swing(6, 120, HIGH, HH),  # continuation while already BULLISH -> BOS
    ]
    trend, last_bos, last_choch = classify_structure(swings)
    assert trend == BULLISH
    assert last_bos is not None
    assert last_bos.kind == BOS
    assert last_bos.direction == BULLISH
    assert last_bos.price == 120


def test_classify_structure_choch_flips_trend_on_counter_break():
    swings = [
        _swing(1, 100, LOW, "L"),
        _swing(2, 110, HIGH, "H"),
        _swing(3, 105, LOW, HL),
        _swing(4, 115, HIGH, HH),  # trend -> BULLISH
        _swing(5, 108, LOW, HL),
        _swing(6, 120, HIGH, HH),  # BOS
        _swing(7, 90, LOW, LL),  # breaks below the last confirmed low -> CHoCH, flips to BEARISH
    ]
    trend, last_bos, last_choch = classify_structure(swings)
    assert trend == BEARISH
    assert last_choch is not None
    assert last_choch.kind == CHOCH
    assert last_choch.direction == BEARISH
    assert last_choch.price == 90


def test_classify_structure_no_swings_is_unclear():
    trend, last_bos, last_choch = classify_structure([])
    assert trend == UNCLEAR
    assert last_bos is None
    assert last_choch is None


# ---- classify_day_type -----------------------------------------------------

def test_classify_day_type_forming_before_ib_completes():
    # Only 2 bars of a 6-bar (30min/5min) IB window -- not enough yet.
    candles = _candles([100, 101])
    result = classify_day_type(candles, ib_minutes=30, bar_minutes=5)
    assert result.day_type == FORMING


def test_classify_day_type_non_trend_day_stays_inside_ib():
    # 6 bars form the IB (100-104), rest of the session stays well within it.
    ib = [100, 102, 104, 101, 103, 100]
    rest = [101, 102, 103, 101, 102, 103, 101, 102]
    candles = _candles(ib + rest)
    result = classify_day_type(candles, ib_minutes=30, bar_minutes=5)
    assert result.day_type == NON_TREND
    assert result.ib_high == 104.3
    assert result.ib_low == 99.7


def test_classify_day_type_trend_day_extends_and_closes_at_extreme():
    ib = [100, 101, 102, 100, 101, 100]  # IB roughly 99.7-102.3, range ~2.6
    # Strong one-directional extension closing right near the session high.
    rest = [104, 108, 112, 116, 120, 124, 128, 132]
    candles = _candles(ib + rest)
    result = classify_day_type(candles, ib_minutes=30, bar_minutes=5)
    assert result.day_type == TREND


def test_classify_day_type_neutral_day_extends_both_sides():
    ib = [100, 101, 102, 100, 101, 100]  # ib ~ 99.7-102.3
    rest = [110, 108, 90, 92, 101, 100]  # extends above AND below IB
    candles = _candles(ib + rest)
    result = classify_day_type(candles, ib_minutes=30, bar_minutes=5)
    assert result.day_type == NEUTRAL


def test_classify_day_type_normal_variation_moderate_one_sided_extension():
    ib = [100, 101, 102, 100, 101, 100]  # ib ~ 99.7-102.3, range ~2.6
    # Extends beyond IB (>1.5x) but not enough to be TREND, and closes back
    # near the middle of the day's range rather than at the extreme.
    rest = [103, 104.5, 104, 103.5, 104, 103.8]
    candles = _candles(ib + rest)
    result = classify_day_type(candles, ib_minutes=30, bar_minutes=5)
    assert result.day_type == NORMAL_VARIATION


# ---- previous day / week high-low -----------------------------------------

def test_previous_day_high_low_picks_most_recent_earlier_session():
    day1 = date(2026, 8, 24)
    day2 = date(2026, 8, 25)
    ts1 = int(pd.Timestamp(day1).timestamp())
    ts2 = int(pd.Timestamp(day2).timestamp())
    candles = pd.DataFrame(
        {
            "ts": [ts1, ts1 + 300, ts2, ts2 + 300],
            "high": [110, 115, 120, 118],
            "low": [105, 108, 112, 111],
            "close": [108, 112, 115, 113],
        }
    )
    result = previous_day_high_low(candles, as_of=day2)
    assert result == (115.0, 105.0)


def test_previous_day_close_matches_last_bar_of_previous_session():
    day1 = date(2026, 8, 24)
    day2 = date(2026, 8, 25)
    ts1 = int(pd.Timestamp(day1).timestamp())
    ts2 = int(pd.Timestamp(day2).timestamp())
    candles = pd.DataFrame(
        {
            "ts": [ts1, ts1 + 300, ts2],
            "high": [110, 115, 120],
            "low": [105, 108, 112],
            "close": [108, 112, 115],
        }
    )
    assert previous_day_close(candles, as_of=day2) == 112.0


def test_previous_day_high_low_none_when_no_earlier_session():
    day1 = date(2026, 8, 24)
    ts1 = int(pd.Timestamp(day1).timestamp())
    candles = pd.DataFrame({"ts": [ts1], "high": [110], "low": [105], "close": [108]})
    assert previous_day_high_low(candles, as_of=day1) is None


def test_previous_week_high_low_uses_most_recent_completed_week():
    # Week 1: Mon 2026-08-17 .. Week 2: Mon 2026-08-24 (as_of falls in week 2)
    w1_mon = date(2026, 8, 17)
    w1_wed = date(2026, 8, 19)
    w2_mon = date(2026, 8, 24)
    ts_mon = int(pd.Timestamp(w1_mon).timestamp())
    ts_wed = int(pd.Timestamp(w1_wed).timestamp())
    ts_w2 = int(pd.Timestamp(w2_mon).timestamp())
    candles = pd.DataFrame(
        {
            "ts": [ts_mon, ts_wed, ts_w2],
            "high": [200, 210, 190],
            "low": [195, 205, 185],
            "close": [198, 208, 188],
        }
    )
    result = previous_week_high_low(candles, as_of=w2_mon)
    assert result == (210.0, 195.0)


# ---- multi-timeframe structure -------------------------------------------


def _five_min_bars(sessions: int, bars_per_session: int, drift: float) -> pd.DataFrame:
    """Ascending 5-minute bars across consecutive weekday sessions."""
    from datetime import date as _date, datetime as _dt, time as _time, timedelta as _td

    rows = []
    day = _date(2026, 8, 3)  # a Monday
    price = 24000.0
    for _ in range(sessions):
        while day.weekday() >= 5:
            day += _td(days=1)
        start = _dt.combine(day, _time(9, 15))
        for i in range(bars_per_session):
            rows.append(
                {
                    "ts": int((start + _td(minutes=5 * i)).timestamp()),
                    "open": price,
                    "high": price + 15,
                    "low": price - 15,
                    "close": price + drift,
                    "volume": 1000,
                }
            )
            price += drift
        day += _td(days=1)
    return pd.DataFrame(rows)


def test_resample_folds_bars_and_keeps_true_extremes():
    bars = _five_min_bars(sessions=1, bars_per_session=12, drift=5.0)
    hourly = market_structure.resample(bars, 60)
    assert len(hourly) == 1  # 12 five-minute bars = one hour
    assert hourly.iloc[0]["high"] == bars["high"].max()
    assert hourly.iloc[0]["low"] == bars["low"].min()
    assert hourly.iloc[0]["close"] == bars["close"].iloc[-1]


def test_daily_resample_never_merges_two_sessions():
    """A 375-minute resample would slice on wall-clock boundaries and blend
    the tail of one session into the head of the next."""
    bars = _five_min_bars(sessions=3, bars_per_session=12, drift=2.0)
    daily = market_structure.resample(bars, None)
    assert len(daily) == 3


def test_hourly_resample_is_anchored_to_the_session_open():
    """Anchored to 09:15, the first hourly bar covers 09:15-10:15. On a plain
    clock-hour resample it would be a 45-minute stub instead."""
    bars = _five_min_bars(sessions=1, bars_per_session=24, drift=1.0)
    hourly = market_structure.resample(bars, 60)
    first = datetime.fromtimestamp(int(hourly.iloc[0]["ts"]))
    assert (first.hour, first.minute) == (9, 15)


def test_multi_timeframe_says_so_rather_than_guessing_on_thin_history():
    """The panel this replaced printed a confident trend for every timeframe.
    With a fortnight of data a daily read has a handful of bars and must say
    that, not pick a direction."""
    bars = _five_min_bars(sessions=10, bars_per_session=75, drift=1.0)
    by_label = {tf.label: tf for tf in market_structure.multi_timeframe(bars)}

    assert by_label["1D"].trend == market_structure.INSUFFICIENT_DATA
    assert by_label["1D"].enough_data is False
    assert "needed before swing structure" in by_label["1D"].note

    assert by_label["5M"].enough_data is True
    assert by_label["5M"].trend in (
        market_structure.BULLISH,
        market_structure.BEARISH,
        market_structure.UNCLEAR,
    )


def test_every_timeframe_is_reported_with_its_own_bar_count():
    bars = _five_min_bars(sessions=8, bars_per_session=75, drift=1.5)
    frames = market_structure.multi_timeframe(bars)
    assert [tf.label for tf in frames] == ["1D", "1H", "15M", "5M"]
    # Higher timeframes must have strictly fewer bars than lower ones.
    counts = [tf.bars for tf in frames]
    assert counts == sorted(counts)
    assert all(tf.note for tf in frames)


def test_summary_exposes_the_timeframe_read():
    bars = _five_min_bars(sessions=8, bars_per_session=75, drift=1.5)
    last_session = pd.to_datetime(bars["ts"].iloc[-1], unit="s").date()
    summary = market_structure.summarize(bars, as_of=last_session)
    assert len(summary.timeframes) == 4
    assert {tf.label for tf in summary.timeframes} == {"1D", "1H", "15M", "5M"}

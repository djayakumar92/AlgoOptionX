"""Price structure and day-type regime -- swing highs/lows, break of
structure (BOS), change of character (CHoCH), and Initial-Balance day-typing.

Grounded in `.claude/skills/nifty-options-domain-knowledge/references/
market-structure-trend.md` (loaded before writing this): swing/BOS/CHoCH via
an N-bar fractal + ATR-scaled minimum-move filter is textbook Dow Theory with
real peer-reviewed backing (Brown, Goetzmann & Kumar 1998); Initial-Balance
day-typing (Steidlmayer, CBOT) is standard professional practice and the
single most actionable finding in that research -- the HLC trade plan
(hlc_strategy.py) is a range-day strategy by construction, and nothing today
checks whether the market is actually behaving like one. Deliberately does
NOT implement order blocks / Fair Value Gaps / ICT-style liquidity sweeps --
the research found no real evidence behind that cluster beyond the
BOS/CHoCH mechanics already covered here.

Not built here (kept honest about scope): multi-timeframe structure and
scored/multi-source support-resistance zones are separate, larger pieces of
the requirement doc (its own later phase) -- this module only covers a single
timeframe's swing structure and day-type regime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

import numpy as np
import pandas as pd

HIGH, LOW = "high", "low"
HH, HL, LH, LL = "HH", "HL", "LH", "LL"
BULLISH, BEARISH, UNCLEAR = "BULLISH", "BEARISH", "UNCLEAR"
BOS, CHOCH = "BOS", "CHOCH"

NON_TREND, NORMAL_VARIATION, TREND, NEUTRAL, FORMING, INSUFFICIENT_DATA = (
    "NON_TREND", "NORMAL_VARIATION", "TREND", "NEUTRAL", "FORMING", "INSUFFICIENT_DATA"
)


@dataclass(frozen=True)
class SwingPoint:
    ts: int
    price: float
    kind: str  # "high" | "low" -- which side of price this swing is
    label: str  # "HH" | "HL" | "LH" | "LL", or "H"/"L" for the first swing of its kind seen


@dataclass(frozen=True)
class StructureEvent:
    kind: str  # BOS | CHOCH
    direction: str  # BULLISH | BEARISH
    ts: int
    price: float
    level: float  # the prior swing price that was broken


@dataclass(frozen=True)
class DayTypeResult:
    day_type: str
    ib_high: float | None
    ib_low: float | None
    session_high: float | None
    session_low: float | None


@dataclass(frozen=True)
class TimeframeStructure:
    """The same swing/BOS read as the 5-minute one, on a higher timeframe.

    `enough_data` matters as much as `trend`. Swing structure needs a run of
    bars before it means anything -- on a daily chart this app has under a
    month of history, which is a handful of bars and not a trend. Saying so is
    the answer; the panel this replaced simply printed "Bullish" for every
    timeframe as a static placeholder.
    """

    label: str  # "1D" | "1H" | "15M" | "5M"
    trend: str  # BULLISH | BEARISH | UNCLEAR | INSUFFICIENT_DATA
    bars: int
    swings: int
    enough_data: bool
    note: str


@dataclass(frozen=True)
class MarketStructureSummary:
    swings: list[SwingPoint]
    structure_trend: str  # BULLISH | BEARISH | UNCLEAR
    last_bos: StructureEvent | None
    last_choch: StructureEvent | None
    day_type: DayTypeResult
    chop: float | None  # today's 14-period Choppiness Index, 0-100
    prev_day_high: float | None
    prev_day_low: float | None
    prev_week_high: float | None
    prev_week_low: float | None
    timeframes: list[TimeframeStructure] = field(default_factory=list)


def _true_range(candles: pd.DataFrame) -> pd.Series:
    high, low, close = candles["high"], candles["low"], candles["close"]
    return pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)


def _atr(candles: pd.DataFrame, period: int = 14) -> pd.Series:
    return _true_range(candles).ewm(alpha=1 / period, adjust=False).mean()


def find_swings(candles: pd.DataFrame, n: int = 3, atr_period: int = 14, atr_mult: float = 0.5) -> list[SwingPoint]:
    """N-bar fractal swing highs/lows, filtered by a minimum ATR-scaled move so
    a few-point wiggle can't pass as a structural swing (per the domain-skill
    research: N=3-5 is the usable range for 5-minute NIFTY bars; a fixed
    N=2 "classic" fractal fires on nearly every minor wiggle).

    Returns confirmed swings in chronological order, each labeled HH/HL/LH/LL
    relative to the previous confirmed swing of the *same* kind (high vs
    low) -- the first swing of each kind is labeled "H"/"L" since there's
    nothing yet to compare it to.
    """
    if len(candles) < 2 * n + 1:
        return []

    candles = candles.reset_index(drop=True)
    highs, lows, ts = candles["high"], candles["low"], candles["ts"]
    atr = _atr(candles, atr_period)

    raw: list[tuple[int, float, str]] = []
    for i in range(n, len(candles) - n):
        if highs.iloc[i] > highs.iloc[i - n : i].max() and highs.iloc[i] > highs.iloc[i + 1 : i + n + 1].max():
            raw.append((i, float(highs.iloc[i]), HIGH))
        if lows.iloc[i] < lows.iloc[i - n : i].min() and lows.iloc[i] < lows.iloc[i + 1 : i + n + 1].min():
            raw.append((i, float(lows.iloc[i]), LOW))
    raw.sort(key=lambda r: r[0])

    # Zigzag pass: candidates of the same kind as the last confirmed swing
    # replace it if more extreme (a fractal high beaten by a later, higher
    # fractal high before any low forms is the "real" swing high); candidates
    # of the opposite kind only confirm if the move clears the ATR filter.
    confirmed: list[list] = []
    for idx, price, kind in raw:
        if not confirmed:
            confirmed.append([idx, price, kind])
            continue
        last_idx, last_price, last_kind = confirmed[-1]
        if kind == last_kind:
            if (kind == HIGH and price > last_price) or (kind == LOW and price < last_price):
                confirmed[-1] = [idx, price, kind]
            continue
        move = abs(price - last_price)
        atr_at = atr.iloc[idx]
        if pd.notna(atr_at) and move >= atr_mult * atr_at:
            confirmed.append([idx, price, kind])

    swings: list[SwingPoint] = []
    prev_high: float | None = None
    prev_low: float | None = None
    for idx, price, kind in confirmed:
        if kind == HIGH:
            label = ("HH" if price > prev_high else "LH") if prev_high is not None else "H"
            prev_high = price
        else:
            label = ("HL" if price > prev_low else "LL") if prev_low is not None else "L"
            prev_low = price
        swings.append(SwingPoint(ts=int(ts.iloc[idx]), price=price, kind=kind, label=label))

    return swings


def classify_structure(swings: list[SwingPoint]) -> tuple[str, StructureEvent | None, StructureEvent | None]:
    """Walks the labeled swing sequence to get the current structural trend
    plus the most recent BOS (continuation) and CHoCH (first counter-trend
    break) events -- both fall directly out of the HH/HL/LH/LL labels:
    a fresh HH while already BULLISH is a BOS, a fresh HH while BEARISH is a
    CHoCH (and flips the trend), mirrored for LL/BEARISH. HL/LH labels
    confirm the existing trend but aren't break events by themselves.

    Documented simplification: "break" here means a swing point's own
    high/low exceeded the prior same-kind swing, not a bar *closing* beyond
    that level intraday -- close enough for a structural read without a
    second bar-by-bar scan, since a fractal high/low is itself a real traded
    price.
    """
    trend = UNCLEAR
    last_bos: StructureEvent | None = None
    last_choch: StructureEvent | None = None
    prev_high_swing: SwingPoint | None = None
    prev_low_swing: SwingPoint | None = None

    for swing in swings:
        if swing.label == HH:
            if trend == BEARISH:
                last_choch = StructureEvent(CHOCH, BULLISH, swing.ts, swing.price, prev_high_swing.price if prev_high_swing else swing.price)
                trend = BULLISH
            elif trend == BULLISH:
                last_bos = StructureEvent(BOS, BULLISH, swing.ts, swing.price, prev_high_swing.price if prev_high_swing else swing.price)
            elif trend == UNCLEAR and prev_low_swing is not None and prev_low_swing.label == HL:
                # HL formed first, this HH confirms it -- Dow Theory pair complete.
                trend = BULLISH
            prev_high_swing = swing
        elif swing.label == LL:
            if trend == BULLISH:
                last_choch = StructureEvent(CHOCH, BEARISH, swing.ts, swing.price, prev_low_swing.price if prev_low_swing else swing.price)
                trend = BEARISH
            elif trend == BEARISH:
                last_bos = StructureEvent(BOS, BEARISH, swing.ts, swing.price, prev_low_swing.price if prev_low_swing else swing.price)
            elif trend == UNCLEAR and prev_high_swing is not None and prev_high_swing.label == LH:
                trend = BEARISH
            prev_low_swing = swing
        elif swing.label == HL:
            prev_low_swing = swing
            if trend == UNCLEAR and prev_high_swing is not None and prev_high_swing.label == HH:
                trend = BULLISH
        elif swing.label == LH:
            prev_high_swing = swing
            if trend == UNCLEAR and prev_low_swing is not None and prev_low_swing.label == LL:
                trend = BEARISH
        else:  # first-ever swing of its kind ("H"/"L") -- nothing to compare yet
            if swing.kind == HIGH:
                prev_high_swing = swing
            else:
                prev_low_swing = swing

    return trend, last_bos, last_choch


# ---- Initial Balance / day-type -----------------------------------------

# Steidlmayer's Market Profile day-typing, simplified to four buckets driven
# by how far the session's range extends beyond the Initial Balance (IB) --
# see market-structure-trend.md for the sourcing. Thresholds below are a
# reasonable, documented reading of the standard rule of thumb, not a
# precisely-sourced number -- treat as a first calibration, not gospel.
_NORMAL_RANGE_MULT = 1.5  # range <= 1.5x IB -> still "normal", not a breakout
_NORMAL_VARIATION_MULT = 2.5  # up to 2.5x IB, one-sided -> normal variation
_TREND_CLOSE_PROXIMITY = 0.25  # close within the outer 25% of the day's range


def initial_balance(session_candles: pd.DataFrame, ib_minutes: int, bar_minutes: int) -> tuple[float, float] | None:
    """High/low of the first ib_minutes of session_candles (already filtered
    to one session, sorted ascending). None if the session hasn't produced
    enough bars yet to form the IB."""
    ib_bars = max(1, ib_minutes // bar_minutes)
    if len(session_candles) < ib_bars:
        return None
    window = session_candles.iloc[:ib_bars]
    return float(window["high"].max()), float(window["low"].min())


def classify_day_type(session_candles: pd.DataFrame, ib_minutes: int = 30, bar_minutes: int = 5) -> DayTypeResult:
    ib = initial_balance(session_candles, ib_minutes, bar_minutes)
    if ib is None:
        return DayTypeResult(FORMING, None, None, None, None)
    ib_high, ib_low = ib
    ib_range = ib_high - ib_low

    session_high = float(session_candles["high"].max())
    session_low = float(session_candles["low"].min())
    last_close = float(session_candles["close"].iloc[-1])

    if ib_range <= 0:
        return DayTypeResult(FORMING, ib_high, ib_low, session_high, session_low)

    up_extension = max(0.0, session_high - ib_high)
    down_extension = max(0.0, ib_low - session_low)
    session_range = session_high - session_low

    if session_range <= _NORMAL_RANGE_MULT * ib_range:
        day_type = NON_TREND
    elif up_extension > 0 and down_extension > 0:
        day_type = NEUTRAL
    elif session_range <= _NORMAL_VARIATION_MULT * ib_range:
        day_type = NORMAL_VARIATION
    else:
        near_high = last_close >= session_high - _TREND_CLOSE_PROXIMITY * session_range
        near_low = last_close <= session_low + _TREND_CLOSE_PROXIMITY * session_range
        day_type = TREND if (near_high or near_low) else NORMAL_VARIATION

    return DayTypeResult(day_type, ib_high, ib_low, session_high, session_low)


# Minimum bars before a swing read on a timeframe is worth reporting. Below
# this the fractal filter and its ATR baseline have too little to work with,
# and whatever comes out is an artefact of the sample size.
_MIN_TIMEFRAME_BARS = 24

_SESSION_OPEN = time(9, 15)

# Label -> minutes. "day" is handled separately, by session date, because a
# 375-minute resample would still slice on wall-clock boundaries and merge the
# tail of one session with the head of the next.
_TIMEFRAMES: list[tuple[str, int | None]] = [
    ("1D", None),
    ("1H", 60),
    ("15M", 15),
    ("5M", 5),
]


def _local_datetimes(ts: pd.Series) -> pd.Series:
    """Epoch seconds as *local* (exchange) wall-clock time.

    `pd.to_datetime(ts, unit="s")` yields UTC, and everything else in this
    project stores and reads these timestamps as local time -- the candles
    come back from the broker in IST and `option_ohlc` builds its session
    bounds with a naive `datetime.combine`. Mixing the two put the 09:15
    session open at 03:45, so an hourly resample anchored to the open was
    anchored to the wrong instant entirely.

    India observes no daylight saving, so a fixed offset taken once is exact
    here; this is not a general-purpose timezone conversion.
    """
    offset = datetime.fromtimestamp(0) - datetime(1970, 1, 1)
    return pd.to_datetime(ts, unit="s") + offset


def resample(candles: pd.DataFrame, minutes: int | None) -> pd.DataFrame:
    """Fold 5-minute bars up to a higher timeframe.

    Anchored to the 09:15 session open rather than the clock hour. A plain
    hourly resample buckets 09:00-10:00, so the first "hour" of the Indian
    session would be 45 minutes long and every later bar would straddle the
    open by 15 minutes. `origin` fixes that.

    `minutes=None` means daily, grouped by session date -- the only grouping
    that cannot merge the end of one session into the start of the next.
    """
    if candles is None or candles.empty or "ts" not in candles.columns:
        return pd.DataFrame()

    frame = candles.copy()
    frame["_dt"] = _local_datetimes(frame["ts"])

    if minutes is None:
        grouped = frame.groupby(frame["_dt"].dt.date)
    else:
        origin = pd.Timestamp.combine(frame["_dt"].iloc[0].date(), _SESSION_OPEN)
        grouped = frame.resample(f"{minutes}min", on="_dt", origin=origin)

    agg = grouped.agg(
        ts=("ts", "first"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna(subset=["close"])

    return agg.reset_index(drop=True)


def multi_timeframe(
    candles: pd.DataFrame, swing_n: int = 3, atr_mult: float = 0.5
) -> list[TimeframeStructure]:
    """Swing-structure direction on each timeframe, highest first.

    Runs exactly the same `find_swings` / `classify_structure` pair the
    5-minute read uses -- deliberately, so "1H is bullish" means the same
    thing there as it does on the chart below it, rather than being a second,
    differently-derived opinion wearing the same word.
    """
    results: list[TimeframeStructure] = []
    for label, minutes in _TIMEFRAMES:
        frame = resample(candles, minutes) if minutes != 5 else candles
        bars = len(frame)

        if bars < _MIN_TIMEFRAME_BARS:
            results.append(
                TimeframeStructure(
                    label=label,
                    trend=INSUFFICIENT_DATA,
                    bars=bars,
                    swings=0,
                    enough_data=False,
                    note=(
                        f"Only {bars} {label} bar(s) stored -- at least {_MIN_TIMEFRAME_BARS} are "
                        "needed before swing structure means anything. This fills in as the app "
                        "runs on more sessions."
                    ),
                )
            )
            continue

        swings = find_swings(frame, n=swing_n, atr_mult=atr_mult)
        trend, _, _ = classify_structure(swings)
        results.append(
            TimeframeStructure(
                label=label,
                trend=trend,
                bars=bars,
                swings=len(swings),
                enough_data=True,
                note=(
                    f"{len(swings)} swing point(s) across {bars} {label} bars."
                    if trend != UNCLEAR
                    else f"{len(swings)} swing point(s) across {bars} {label} bars, with no "
                    "consistent sequence of higher highs or lower lows."
                ),
            )
        )
    return results


def choppiness_index(candles: pd.DataFrame, period: int = 14) -> pd.Series:
    """Standard CHOP formula, 0-100. Complements ADX (trend *strength*) with
    a read on trend *presence* -- low CHOP + rising ADX together is a
    stronger "trending regime" signal than either alone, per the domain
    research. Secondary/supporting field, not a primary regime driver here."""
    tr_sum = _true_range(candles).rolling(period).sum()
    high_max = candles["high"].rolling(period).max()
    low_min = candles["low"].rolling(period).min()
    rng = (high_max - low_min).replace(0, np.nan)
    return 100 * np.log10(tr_sum / rng) / np.log10(period)


# ---- previous day / week high-low ----------------------------------------

def _session_dates(candles: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(candles["ts"], unit="s").dt.date


def session_slice(candles: pd.DataFrame, target_date: date) -> pd.DataFrame:
    dates = _session_dates(candles)
    return candles[dates == target_date]


def _previous_trading_date(candles: pd.DataFrame, as_of: date) -> date | None:
    dates = sorted({d for d in _session_dates(candles) if d < as_of})
    return dates[-1] if dates else None


def previous_day_high_low(candles: pd.DataFrame, as_of: date) -> tuple[float, float] | None:
    prev_date = _previous_trading_date(candles, as_of)
    if prev_date is None:
        return None
    prev = session_slice(candles, prev_date)
    if prev.empty:
        return None
    return float(prev["high"].max()), float(prev["low"].min())


def previous_day_close(candles: pd.DataFrame, as_of: date) -> float | None:
    """Previous trading session's last close -- for classic_pivots, which
    needs H/L/C together, not just the H/L that previous_day_high_low gives."""
    prev_date = _previous_trading_date(candles, as_of)
    if prev_date is None:
        return None
    prev = session_slice(candles, prev_date)
    if prev.empty:
        return None
    return float(prev["close"].iloc[-1])


def previous_week_high_low(candles: pd.DataFrame, as_of: date) -> tuple[float, float] | None:
    """The most recently *completed* Mon-Sun calendar week strictly before
    as_of's own week -- not a trailing 7-day window."""
    dates = _session_dates(candles)
    iso = pd.to_datetime(candles["ts"], unit="s").dt.isocalendar()
    this_week = (as_of.isocalendar().year, as_of.isocalendar().week)
    week_keys = list(zip(iso["year"], iso["week"]))
    mask = [wk < this_week for wk in week_keys]
    if not any(mask):
        return None
    prior_weeks = sorted({wk for wk, m in zip(week_keys, mask) if m})
    if not prior_weeks:
        return None
    last_week = prior_weeks[-1]
    week_mask = [wk == last_week for wk in week_keys]
    subset = candles[pd.Series(week_mask, index=candles.index)]
    if subset.empty:
        return None
    return float(subset["high"].max()), float(subset["low"].min())


# ---- top-level summary ----------------------------------------------------

def summarize(
    candles: pd.DataFrame,
    as_of: date,
    swing_n: int = 3,
    atr_mult: float = 0.5,
    ib_minutes: int = 30,
    bar_minutes: int = 5,
    recent_swings: int = 8,
) -> MarketStructureSummary:
    """candles: ascending-ts 5-minute bars for one symbol, however much
    history is locally available (see repository.get_candles) -- degrades
    field-by-field rather than failing outright when history is short."""
    swings = find_swings(candles, n=swing_n, atr_mult=atr_mult)
    trend, last_bos, last_choch = classify_structure(swings)

    today = session_slice(candles, as_of)
    day_type = classify_day_type(today, ib_minutes=ib_minutes, bar_minutes=bar_minutes) if not today.empty else DayTypeResult(
        INSUFFICIENT_DATA, None, None, None, None
    )

    chop_series = choppiness_index(today) if len(today) >= 14 else None
    chop = float(chop_series.iloc[-1]) if chop_series is not None and pd.notna(chop_series.iloc[-1]) else None

    prev_day = previous_day_high_low(candles, as_of)
    prev_week = previous_week_high_low(candles, as_of)

    return MarketStructureSummary(
        swings=swings[-recent_swings:],
        structure_trend=trend,
        last_bos=last_bos,
        last_choch=last_choch,
        day_type=day_type,
        chop=round(chop, 1) if chop is not None else None,
        prev_day_high=prev_day[0] if prev_day else None,
        prev_day_low=prev_day[1] if prev_day else None,
        prev_week_high=prev_week[0] if prev_week else None,
        prev_week_low=prev_week[1] if prev_week else None,
        timeframes=multi_timeframe(candles, swing_n=swing_n, atr_mult=atr_mult),
    )

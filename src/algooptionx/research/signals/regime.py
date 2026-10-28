"""Regime layer: *what kind of day is this, and is option premium currently
cheap or rich?* -- i.e. the buy-vs-sell decision, made once, explicitly,
before any individual setup is scored.

Why this module exists. Everything the analyzer had before this answered
"which way is the market leaning" (bullish/bearish). Nothing answered the
question that actually decides whether you should be an option **buyer** or
an option **seller** today. Those are separate questions, and getting the
second one wrong is what turns a correct directional call into a losing
trade -- buying premium into a flat, richly-priced, positive-gamma session
loses money even when the direction is right, because theta and the
volatility risk premium both work against the buyer.

## The primary measure: realized vs implied movement

The ATM straddle price is the market's own priced expectation of how far the
underlying moves by expiry. Compare that against how far the underlying
*actually* has been moving, and the gap is the volatility risk premium (VRP):

- realized movement < implied  -> premium is rich -> **selling is favored**
- realized movement > implied  -> premium is cheap -> **buying is favored**

VRP is normally positive (implied exceeds realized) across index options
worldwide -- which is the honest, structural reason why premium selling wins
more often than it loses, and why this project's existing HLC rule is a
seller's rule. This module makes that assumption explicit and, more
importantly, **measurable**, so the analyzer can notice the days when it
stops being true instead of selling into them blindly.

## Everything else is a modifier, and every modifier is traceable

`stance_score` is a signed sum of individually-listed factors (see
`RegimeReason`): positive points argue for buying premium, negative for
selling it. No factor is hidden, none is multiplied by an unexplained
weight, and the reasons list is meant to be rendered verbatim to the user.
The weights themselves are a documented first calibration reflecting the
domain research's qualitative rankings -- they are not fitted to data, and
`calibration.py` exists to check them against outcomes over time rather than
leaving them permanently unexamined.

Grounded in the domain-knowledge skill's `greeks-iv-timing.md` (theta/gamma
by time-of-day and expiry-day, IV behaviour around the open) and
`market-structure-trend.md` (Initial-Balance day typing as the
best-evidenced regime read available), plus `gex.py` for the dealer-hedging
regime.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd

from algooptionx.research.signals import gex as gex_module
from algooptionx.research.signals import market_structure as ms
from algooptionx.research.signals.trend import TrendSummary

TRENDING, RANGING, TRANSITIONAL, REGIME_UNKNOWN = "TRENDING", "RANGING", "TRANSITIONAL", "UNKNOWN"
RICH, FAIR, CHEAP, PRICING_UNKNOWN = "RICH", "FAIR", "CHEAP", "UNKNOWN"
BUY_FAVORED, SELL_FAVORED, NEUTRAL_STANCE = "BUY_FAVORED", "SELL_FAVORED", "NEUTRAL"

TUESDAY = 1  # NIFTY weekly expiry weekday since 1 Sept 2025 (SEBI circular) -- was Thursday before

# Trading days per calendar week, used to convert an expiry that is N calendar
# days away into the sqrt-of-time scaling factor for the straddle.
_TRADING_DAYS_PER_WEEK = 5.0

# VRP bands. Ratio = realized daily movement / implied daily movement.
# +/-15% around parity is treated as "fair" -- wide enough that ordinary
# estimation noise in a short ATR sample doesn't flip the stance every day.
_VRP_CHEAP_RATIO = 1.15  # realized exceeds implied by 15%+ -> premium is cheap
_VRP_RICH_RATIO = 0.85

# Minimum daily observations before the realized-movement estimate is trusted
# enough to drive the stance at full weight. Below this the VRP factor still
# reports, but at reduced weight and with an explicit low-sample warning.
_MIN_DAILY_SAMPLE = 20

_IV_RICH_PCTL = 70.0
_IV_CHEAP_PCTL = 30.0

# Factor weights, buy-premium positive. Ordered by the domain research's own
# confidence ranking: the realized-vs-implied comparison is the only factor
# here that measures the actual economics of the buy-vs-sell choice, so it
# carries the most weight; day-type and structure are well-evidenced regime
# reads; gamma regime and IV percentile are supporting context.
_W_VRP = 30.0
_W_STRUCTURE = 20.0
_W_DAY_TYPE = 15.0
_W_GAMMA = 15.0
_W_IV_PCTL = 15.0
_W_EXPIRY = 10.0

_STANCE_THRESHOLD = 25.0


@dataclass(frozen=True)
class RegimeReason:
    """One traceable contribution to stance_score. Rendered verbatim in the UI --
    the user should never see a number they cannot trace to a sentence."""

    factor: str
    reading: str
    points: float  # signed; positive argues for buying premium
    explanation: str


@dataclass(frozen=True)
class RegimeSummary:
    as_of: str

    # --- movement pricing (the primary measure) ---
    atm_strike: float | None
    straddle_price: float | None  # ATM CE + PE, the market's priced move to expiry
    days_to_expiry: int | None
    implied_daily_move_points: float | None  # straddle scaled to one session
    realized_daily_move_points: float | None  # average absolute close-to-close move
    realized_daily_range_points: float | None  # average true range -- for sizing levels, not pricing
    realized_sample_days: int
    move_edge_ratio: float | None  # realized / implied
    premium_pricing: str  # RICH | FAIR | CHEAP | UNKNOWN

    # --- regime context ---
    structure_regime: str  # TRENDING | RANGING | TRANSITIONAL | UNKNOWN
    day_type: str
    gamma_regime: str
    gamma_flip_strike: float | None
    iv_percentile: float | None
    adx: float | None
    chop: float | None
    session_window: str
    is_expiry_day: bool

    # --- the decision ---
    premium_stance: str  # BUY_FAVORED | SELL_FAVORED | NEUTRAL
    stance_score: float  # -100..+100, positive = buy premium
    stance_confidence: float  # 0-100, |score| rescaled -- how decisive the factors are
    reasons: list[RegimeReason] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- helpers --


def is_expiry_day(as_of: date, tracked_expiry: date | None = None) -> bool:
    """True when as_of is the weekly/monthly expiry session.

    Prefers the actual tracked expiry date from the feed (which correctly
    reflects holiday-shifted expiries) and falls back to the Tuesday weekday
    rule only when no expiry is known. The weekday fallback is deliberately
    Tuesday, not Thursday: NIFTY weekly expiry moved on 1 Sept 2025.
    """
    if tracked_expiry is not None:
        return as_of == tracked_expiry
    return as_of.weekday() == TUESDAY


def trading_days_to_expiry(as_of: date, expiry: date | None) -> int | None:
    """Whole trading days from as_of to expiry inclusive of the expiry session.

    Weekend-skipping only (no NSE holiday calendar in this project -- see
    option_ohlc.last_completed_trading_day for the same limitation), so this
    can overcount by one across a holiday week. Used only as the sqrt-of-time
    divisor, where a one-day error is second-order.
    """
    if expiry is None or expiry < as_of:
        return None
    days = np.busday_count(as_of.isoformat(), expiry.isoformat())
    return max(1, int(days) + 1)


def atm_straddle(chain: pd.DataFrame, spot_price: float) -> tuple[float | None, float | None]:
    """(atm_strike, CE+PE last price at that strike).

    ATM here is nearest-strike-to-spot, which is the right definition for a
    *pricing* read. Note this differs from hlc_strategy.select_atm(), which
    picks the strike with the smallest |CE-PE| premium gap -- that one
    replicates the user's spreadsheet and is intentionally left alone.
    """
    if chain.empty:
        return None, None
    strikes = chain["strike"].dropna().unique()
    if len(strikes) == 0:
        return None, None

    atm = float(min(strikes, key=lambda s: abs(s - spot_price)))
    at_strike = chain[chain["strike"] == atm]
    ce = at_strike[at_strike["option_type"] == "CE"]["ltp"]
    pe = at_strike[at_strike["option_type"] == "PE"]["ltp"]
    if ce.empty or pe.empty or pd.isna(ce.iloc[0]) or pd.isna(pe.iloc[0]):
        return atm, None
    return atm, float(ce.iloc[0]) + float(pe.iloc[0])


def implied_daily_move(straddle_price: float | None, days_to_expiry: int | None) -> float | None:
    """Convert a straddle priced to expiry into a one-session expected move.

    The ATM straddle approximates the expected absolute move of the
    underlying by expiry; movement scales with the square root of time, so
    one session's share is straddle / sqrt(sessions remaining). Standard
    practitioner approximation -- accurate enough for a rich/cheap
    comparison, not a substitute for a proper option-pricing model.
    """
    if straddle_price is None or not days_to_expiry:
        return None
    return straddle_price / math.sqrt(days_to_expiry)


# Two consecutive stored sessions more than this many calendar days apart are
# treated as a hole in the data, not a real overnight move. Four days spans a
# long weekend; anything wider is missing history, and its "true range" would
# be a multi-week move masquerading as one session's.
_MAX_SESSION_GAP_DAYS = 4


def daily_from_intraday(candles: pd.DataFrame) -> pd.DataFrame:
    """Rebuild daily OHLC by folding stored 5-minute bars into sessions.

    Preferred over the broker's own daily-candle endpoint, for two reasons
    found the hard way in this project. First, that endpoint stamps each
    daily candle at midnight of the *following* calendar day (documented in
    `ingestion/option_ohlc.py`, confirmed live), so querying it by date
    silently returns the wrong session. Second, the daily rows this app has
    actually accumulated contain month-wide holes, and a "true range" taken
    across a five-week hole is a five-week move being counted as one day --
    which inflated the realized-movement estimate to more than twice its real
    value the first time this ran against live data.

    The intraday bars have neither problem: each bar's timestamp falls
    naturally inside the session it belongs to, and they are refreshed every
    minute the app is running.
    """
    if candles is None or candles.empty or "ts" not in candles.columns:
        return pd.DataFrame()

    frame = candles.copy()
    # Local exchange time, not UTC -- see market_structure._local_datetimes.
    # For IST the two happen to land on the same calendar date because the
    # whole session sits inside one UTC day, but relying on that is how the
    # hourly resample ended up anchored to 03:45.
    frame["session"] = ms._local_datetimes(frame["ts"]).dt.date
    grouped = frame.groupby("session", sort=True).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
    )
    return grouped.reset_index()


def realized_daily_move(
    daily_candles: pd.DataFrame, period: int = 14, intraday_candles: pd.DataFrame | None = None
) -> tuple[float | None, int]:
    """(average absolute close-to-close move in points, sample size).

    **Displacement, not range, and the distinction is the whole point.** A
    straddle pays out on |final price - strike|: how far the underlying ends
    up from where it started, not how much ground it covered getting there.
    Measuring realized movement as average true range instead -- the first
    version of this function did exactly that -- compares a range against a
    displacement, and since a session's high-low range is typically 1.5 to 2
    times its net move, it overstates realized movement by that same factor.

    That error is not symmetric or harmless: it biases every reading toward
    "options are cheap, buy premium", which is the more expensive side to be
    wrong on. Caught by the first live run against stored data, where it
    reported movement at more than twice the priced move on a perfectly
    ordinary week.

    Sessions rebuilt from intraday bars take precedence over stored daily
    candles (see `daily_from_intraday`), and moves spanning a gap in the data
    are dropped rather than counted as one session's.
    """
    source = _movement_source(daily_candles, intraday_candles)
    if source is None or len(source) < 2:
        return None, 0 if source is None else len(source)

    moves = source["close"].diff().abs()
    moves = _drop_gap_rows(moves, source)
    if moves.empty:
        return None, len(source)

    value = float(moves.tail(min(period, len(moves))).mean())
    return (value if math.isfinite(value) else None), int(len(moves))


def realized_daily_range(
    daily_candles: pd.DataFrame, period: int = 14, intraday_candles: pd.DataFrame | None = None
) -> tuple[float | None, int]:
    """(average true range in points, sample size).

    Kept separate from `realized_daily_move` and used for a different job:
    range is the right scale for *placing levels* -- how far a target or a
    stop should sit -- while displacement is the right scale for *pricing*
    comparisons. Conflating them is the mistake documented above.
    """
    source = _movement_source(daily_candles, intraday_candles)
    if source is None or len(source) < 2:
        return None, 0 if source is None else len(source)

    tr = pd.concat(
        [
            source["high"] - source["low"],
            (source["high"] - source["close"].shift()).abs(),
            (source["low"] - source["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    tr = _drop_gap_rows(tr, source)
    if tr.empty:
        return None, len(source)

    value = float(tr.tail(min(period, len(tr))).mean())
    return (value if math.isfinite(value) else None), int(len(tr))


def _movement_source(
    daily_candles: pd.DataFrame, intraday_candles: pd.DataFrame | None
) -> pd.DataFrame | None:
    rebuilt = daily_from_intraday(intraday_candles) if intraday_candles is not None else pd.DataFrame()
    source = daily_candles
    if not rebuilt.empty and (source is None or source.empty or len(rebuilt) >= len(source)):
        source = rebuilt
    if source is None or source.empty:
        return None
    usable = source.dropna(subset=["high", "low", "close"]).copy()
    return usable if not usable.empty else None


def _drop_gap_rows(series: pd.Series, source: pd.DataFrame) -> pd.Series:
    """Remove values whose two sessions are further apart than a long weekend.

    Without this, the five-week hole sitting in this app's stored daily
    candles produces a single "day" whose move is a five-week trend.
    """
    if "session" in source.columns:
        sessions = pd.to_datetime(source["session"])
    elif "ts" in source.columns:
        sessions = ms._local_datetimes(source["ts"])
    else:
        return series.dropna()

    gap_days = sessions.diff().dt.days
    return series[(gap_days.isna()) | (gap_days <= _MAX_SESSION_GAP_DAYS)].dropna()


def iv_percentile(current_iv: float | None, iv_history: list[float]) -> float | None:
    """Where current ATM IV sits within its own stored history, 0-100.

    Distinct from momentum.iv_rank(), which is scoped to the current session
    only: this one is fed from the persisted option-chain snapshots, so it
    grows into a genuine multi-day/multi-week percentile as the ledger
    accumulates. Returns None below 20 observations rather than reporting a
    percentile that a handful of points cannot support.
    """
    if current_iv is None or len(iv_history) < 20:
        return None
    arr = np.asarray([v for v in iv_history if v is not None and math.isfinite(v)], dtype=float)
    if arr.size < 20:
        return None
    return round(float((arr < current_iv).mean() * 100), 1)


def classify_structure_regime(adx: float | None, chop: float | None, day_type: str) -> str:
    """Trending vs ranging, from three partly-independent reads.

    ADX measures trend *strength*, CHOP measures trend *presence*, and IB
    day-typing measures what today has actually done so far. The domain
    research notes low CHOP + rising ADX together is a stronger read than
    either alone; day-type is given veto-strength on the range side because
    a NON_TREND day (session range barely exceeding the initial balance) is
    a direct observation, not an indicator inference.
    """
    votes_trend = 0
    votes_range = 0

    if adx is not None:
        if adx >= 25:
            votes_trend += 1
        elif adx < 20:
            votes_range += 1

    if chop is not None:
        if chop <= 38.2:
            votes_trend += 1
        elif chop >= 61.8:
            votes_range += 1

    if day_type == ms.TREND:
        votes_trend += 2
    elif day_type == ms.NON_TREND:
        votes_range += 2
    elif day_type == ms.NORMAL_VARIATION:
        votes_trend += 1

    if votes_trend == 0 and votes_range == 0:
        return REGIME_UNKNOWN
    if votes_trend > votes_range:
        return TRENDING
    if votes_range > votes_trend:
        return RANGING
    return TRANSITIONAL


# ------------------------------------------------------------- the engine --


def summarize(
    *,
    spot_price: float,
    chain: pd.DataFrame,
    daily_candles: pd.DataFrame,
    intraday_candles: pd.DataFrame | None = None,
    structure: ms.MarketStructureSummary | None = None,
    gex_summary: gex_module.GexSummary | None,
    trend: TrendSummary | None = None,
    iv_history: list[float] | None = None,
    current_atm_iv: float | None = None,
    tracked_expiry: date | None = None,
    now: datetime | None = None,
    session_window: str = "MIDDAY",
) -> RegimeSummary:
    now = now or datetime.now()
    as_of = now.date()
    reasons: list[RegimeReason] = []
    warnings: list[str] = []
    score = 0.0

    atm, straddle = atm_straddle(chain, spot_price)
    dte = trading_days_to_expiry(as_of, tracked_expiry)
    implied = implied_daily_move(straddle, dte)
    realized, sample_days = realized_daily_move(daily_candles, intraday_candles=intraday_candles)
    realized_range, _ = realized_daily_range(daily_candles, intraday_candles=intraday_candles)

    # --- factor 1: realized vs implied movement (the primary measure) ----
    ratio = None
    pricing = PRICING_UNKNOWN
    # `is not None`, not truthiness: a genuinely motionless market has a
    # realized move of exactly 0.0, which is the strongest possible reading
    # that premium is rich -- and a truthiness check silently drops it.
    if implied is not None and realized is not None and implied > 0:
        ratio = round(realized / implied, 3)
        low_sample = sample_days < _MIN_DAILY_SAMPLE
        weight = _W_VRP * (0.5 if low_sample else 1.0)

        if ratio >= _VRP_CHEAP_RATIO:
            pricing, points = CHEAP, weight
            detail = (
                f"NIFTY has been finishing about {realized:.0f} points away from where it opened, while the "
                f"ATM straddle prices only about {implied:.0f} points of movement for a session. Movement is underpriced, "
                "which is the condition that favours buying options rather than selling them."
            )
        elif ratio <= _VRP_RICH_RATIO:
            pricing, points = RICH, -weight
            detail = (
                f"The ATM straddle prices about {implied:.0f} points of movement per session, but "
                f"NIFTY has actually been finishing about {realized:.0f} points from its open. Options are priced richer "
                "than recent movement justifies -- the normal state, and the seller's edge."
            )
        else:
            pricing, points = FAIR, 0.0
            detail = (
                f"Priced movement ({implied:.0f} points) and actual recent movement "
                f"({realized:.0f} points) are close enough to call fair. Neither side of the "
                "premium has a pricing edge today; the trade has to come from structure instead."
            )

        if low_sample:
            detail += (
                f" Weight halved: only {sample_days} days of daily history are stored, "
                f"below the {_MIN_DAILY_SAMPLE} needed to trust this estimate fully."
            )
            warnings.append(
                f"Realized-movement estimate is based on {sample_days} days of history. "
                "It will get more reliable as the app stores more sessions."
            )

        score += points
        reasons.append(
            RegimeReason(
                factor="Premium pricing (realized vs implied move)",
                reading=f"{pricing} (ratio {ratio})",
                points=round(points, 1),
                explanation=detail,
            )
        )
    else:
        warnings.append(
            "Could not compare real movement against priced movement -- needs both a live ATM "
            "straddle price and stored daily candles. The stance below rests on the other factors only."
        )

    # --- factor 2: structure regime -------------------------------------
    adx = trend.adx if trend else None
    chop = structure.chop if structure else None
    day_type = structure.day_type.day_type if structure else ms.INSUFFICIENT_DATA
    structure_regime = classify_structure_regime(adx, chop, day_type)

    if structure_regime == TRENDING:
        score += _W_STRUCTURE
        reasons.append(
            RegimeReason(
                "Market structure",
                "Trending",
                _W_STRUCTURE,
                "Price is making directional progress rather than rotating in a range. Trending "
                "sessions are where bought options can outrun their own time decay.",
            )
        )
    elif structure_regime == RANGING:
        score -= _W_STRUCTURE
        reasons.append(
            RegimeReason(
                "Market structure",
                "Ranging",
                -_W_STRUCTURE,
                "Price is rotating rather than trending. In a range, a bought option pays time "
                "decay for movement that never arrives -- this is seller territory.",
            )
        )
    else:
        reasons.append(
            RegimeReason(
                "Market structure",
                structure_regime.title(),
                0.0,
                "Structure is not clearly trending or ranging yet, so it argues for neither side.",
            )
        )

    # --- factor 3: today's day type (direct observation) -----------------
    if day_type == ms.TREND:
        score += _W_DAY_TYPE
        reasons.append(
            RegimeReason(
                "Day type (initial balance)",
                "Trend day",
                _W_DAY_TYPE,
                "Today has extended well beyond its first-30-minute range and is holding near the "
                "extreme -- the day profile in which selling premium gets run over.",
            )
        )
    elif day_type == ms.NON_TREND:
        score -= _W_DAY_TYPE
        reasons.append(
            RegimeReason(
                "Day type (initial balance)",
                "Non-trend day",
                -_W_DAY_TYPE,
                "Today's whole range has stayed close to its first-30-minute range. Contained days "
                "are the ones premium selling is built for.",
            )
        )
    else:
        reasons.append(
            RegimeReason(
                "Day type (initial balance)",
                day_type.replace("_", " ").title(),
                0.0,
                "Day type is not decisive yet -- the initial balance either has not formed or the "
                "session has not committed to a profile.",
            )
        )

    # --- factor 4: dealer gamma regime -----------------------------------
    gamma_regime = gex_summary.regime if gex_summary else gex_module.GAMMA_UNKNOWN
    if gamma_regime == gex_module.NEGATIVE_GAMMA:
        score += _W_GAMMA
        reasons.append(
            RegimeReason(
                "Dealer gamma",
                "Negative",
                _W_GAMMA,
                "Hedging flow currently pushes with moves instead of against them, so moves tend to "
                "extend rather than get pinned. Good for buyers, dangerous for sellers.",
            )
        )
    elif gamma_regime == gex_module.POSITIVE_GAMMA:
        score -= _W_GAMMA
        reasons.append(
            RegimeReason(
                "Dealer gamma",
                "Positive",
                -_W_GAMMA,
                "Hedging flow currently leans against moves -- rallies get sold, dips get bought. "
                "That damping is what keeps a sold option's premium decaying.",
            )
        )
    else:
        reasons.append(
            RegimeReason(
                "Dealer gamma",
                "Unknown",
                0.0,
                "Gamma data was not available in this chain snapshot (greeks only arrive during "
                "market hours), so this factor is neutral.",
            )
        )

    # --- factor 5: IV percentile -----------------------------------------
    iv_pctl = iv_percentile(current_atm_iv, iv_history or [])
    if iv_pctl is None:
        reasons.append(
            RegimeReason(
                "Implied volatility level",
                "Not enough history",
                0.0,
                "At least 20 stored volatility readings are needed before a percentile means "
                "anything. This factor stays neutral until then.",
            )
        )
    elif iv_pctl >= _IV_RICH_PCTL:
        score -= _W_IV_PCTL
        reasons.append(
            RegimeReason(
                "Implied volatility level",
                f"{iv_pctl:.0f}th percentile -- high",
                -_W_IV_PCTL,
                "Volatility is priced near the top of its own recent range. Buying here means paying "
                "up, and any volatility drop works against the position.",
            )
        )
    elif iv_pctl <= _IV_CHEAP_PCTL:
        score += _W_IV_PCTL
        reasons.append(
            RegimeReason(
                "Implied volatility level",
                f"{iv_pctl:.0f}th percentile -- low",
                _W_IV_PCTL,
                "Volatility is priced near the bottom of its own recent range, so options are "
                "relatively cheap and a volatility expansion would help a buyer.",
            )
        )
    else:
        reasons.append(
            RegimeReason(
                "Implied volatility level",
                f"{iv_pctl:.0f}th percentile -- middling",
                0.0,
                "Volatility is mid-range, offering no edge to either side.",
            )
        )

    # --- factor 6: expiry-day theta ---------------------------------------
    expiry_today = is_expiry_day(as_of, tracked_expiry)
    if expiry_today:
        score -= _W_EXPIRY
        reasons.append(
            RegimeReason(
                "Expiry day",
                "Yes",
                -_W_EXPIRY,
                "Time decay is at its most violent today, which is a structural pull in the seller's "
                "favour. It comes with the session's highest gamma risk too -- see the risk warning.",
            )
        )
        warnings.append(
            "Expiry day: an option's sensitivity to NIFTY changes fastest today, so a stop sized off "
            "a calm morning candle can be blown through far quicker than usual. Size down."
        )

    if session_window == "OPENING":
        warnings.append(
            "First 30 minutes: volatility is still unwinding from the overnight gap and direction is "
            "unresolved. Most professional intraday sellers do not open new positions in this window."
        )

    stance = NEUTRAL_STANCE
    if score >= _STANCE_THRESHOLD:
        stance = BUY_FAVORED
    elif score <= -_STANCE_THRESHOLD:
        stance = SELL_FAVORED

    max_possible = _W_VRP + _W_STRUCTURE + _W_DAY_TYPE + _W_GAMMA + _W_IV_PCTL + _W_EXPIRY
    stance_confidence = round(min(100.0, abs(score) / max_possible * 100), 1)

    return RegimeSummary(
        as_of=now.isoformat(timespec="seconds"),
        atm_strike=atm,
        straddle_price=round(straddle, 2) if straddle is not None else None,
        days_to_expiry=dte,
        implied_daily_move_points=round(implied, 1) if implied is not None else None,
        realized_daily_move_points=round(realized, 1) if realized is not None else None,
        realized_daily_range_points=round(realized_range, 1) if realized_range is not None else None,
        realized_sample_days=sample_days,
        move_edge_ratio=ratio,
        premium_pricing=pricing,
        structure_regime=structure_regime,
        day_type=day_type,
        gamma_regime=gamma_regime,
        gamma_flip_strike=gex_summary.gamma_flip_strike if gex_summary else None,
        iv_percentile=iv_pctl,
        adx=adx,
        chop=chop,
        session_window=session_window,
        is_expiry_day=expiry_today,
        premium_stance=stance,
        stance_score=round(score, 1),
        stance_confidence=stance_confidence,
        reasons=reasons,
        warnings=warnings,
    )

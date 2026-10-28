"""The setup engine: named, precondition-gated trade setups -- both option
buying and option selling -- each with an explicit assumption, an explicit
trigger, an explicit invalidation, and a score that can be traced line by
line back to the readings that produced it.

## Why this replaces vote-counting

`combine.py` produces a bias by counting four signal groups as equal votes.
That is fine as a display, but it is not a trade: it never says *what would
have to happen* for you to enter, *what assumption you are making*, or *what
would prove you wrong*. It also has no notion of buying versus selling
premium -- it always suggests buying an option, which is the wrong side of
the trade on most NIFTY sessions.

Each setup here is instead a hypothesis with a falsifiable shape:

- **Gates** are hard preconditions. If any gate fails, the setup does not
  fire at all -- it cannot be rescued by a high score elsewhere. This is the
  single most important structural difference from vote-counting, where
  enough weak agreement could always manufacture a signal.
- **Evidence** is the weighted scoring that runs only once the gates pass.
  Weights per setup sum to 100, so `score` reads directly as "how much of
  this setup's ideal case is actually present".
- **Assumption / trigger / invalidation** are stated in plain language on
  every signal, because a setup you cannot argue against is a setup you
  cannot manage.

## Honesty rules this module holds to

1. `score` is evidence present, not probability of profit. Those are
   different things and the field names keep them different.
2. Historical hit rate is attached only from real graded outcomes in the
   ledger (see `calibration.py`), always with its sample size, and it
   **lowers** the grade when the sample is thin rather than being quietly
   omitted. A setup with no history says so.
3. Nothing here places or sizes an order. Sizing stays in `risk.py`, which
   already knows about the gamma windows that matter.

Grounded in the domain-knowledge skill: Initial-Balance day typing and
swing/BOS structure from `market-structure-trend.md`; OI wall freshness and
the volume-to-OI unwinding warning from
`oi-pcr-institutional-practice.md` §3; gamma/theta time-of-day and
expiry-day behaviour from `greeks-iv-timing.md`; and the deliberate
*absence* of order-block / fair-value-gap / liquidity-sweep setups, which
that same research found to be marketing rather than evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from algooptionx.research.signals import gex as gex_module
from algooptionx.research.signals import market_structure as ms
from algooptionx.research.signals import regime as regime_module
from algooptionx.research.signals.oi_walls import OiWall
from algooptionx.research.signals.trend import TrendSummary

BUY_CE, BUY_PE, SELL_CE, SELL_PE, SELL_STRADDLE = "BUY_CE", "BUY_PE", "SELL_CE", "SELL_PE", "SELL_STRADDLE"
BUY_PREMIUM, SELL_PREMIUM = "BUY_PREMIUM", "SELL_PREMIUM"
BULLISH, BEARISH, NEUTRAL = "BULLISH", "BEARISH", "NEUTRAL"

ARMED, BLOCKED = "ARMED", "BLOCKED"

# Readiness: where price is *right now* relative to the level the setup keys
# on. A setup being armed says the conditions are right; readiness says
# whether to act this minute, which is a different question and the one that
# actually matters with the market open.
WAIT, NOW, MISSED, READINESS_NA = "WAIT", "NOW", "MISSED", "NA"

# Once price has run this far past a trigger, taking the entry is chasing:
# the stop is now that much further away, so the same trade carries a worse
# risk-to-reward than the one the setup was scored on. Expressed as a
# fraction of the day's expected move so it scales with volatility.
_CHASE_FRACTION = 0.25

# How close price must be to a level being sold before that sale is live --
# a sell-the-rejection setup is not actionable while price is nowhere near
# the level it depends on.
_AT_LEVEL_FRACTION = 0.25

# Grade bands on the evidence score, before the sample-size penalty.
_GRADE_A, _GRADE_B, _GRADE_C = 75.0, 60.0, 45.0

# Below this many graded outcomes, a setup's grade is capped -- see _grade().
# The cap is deliberately aggressive: this project has repeatedly chosen to
# show "not enough data" over a confident-looking number built on three
# trades.
_MIN_TRUSTED_SAMPLE = 20

# How close spot must be to a level for a setup keyed on that level to arm,
# as a fraction of the day's expected move. Scaling by expected move rather
# than a fixed point count means the same rule behaves sensibly on a 60-point
# day and a 250-point day.
_PROXIMITY_FRACTION = 0.35

# Fallback expected move (points) when the regime layer could not compute one
# -- roughly a quiet NIFTY session. Only ever used for proximity scaling, and
# any setup relying on it says so in its own warning.
_FALLBACK_EXPECTED_MOVE = 90.0


@dataclass(frozen=True)
class Gate:
    """A hard precondition. All must pass or the setup does not fire."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Evidence:
    """One weighted, earned contribution to a setup's score."""

    name: str
    reading: str
    earned: float
    weight: float
    detail: str


@dataclass(frozen=True)
class CalibrationRead:
    """What actually happened the last time this setup fired. Filled in from
    the ledger by `calibration.py`; None means it has never been graded."""

    sample_size: int
    wins: int
    hit_rate: float | None  # 0-100
    avg_points: float | None
    note: str


@dataclass(frozen=True)
class SetupSignal:
    key: str
    name: str
    action: str  # BUY_CE | BUY_PE | SELL_CE | SELL_PE | SELL_STRADDLE
    side: str  # BUY_PREMIUM | SELL_PREMIUM
    direction: str  # view on the underlying: BULLISH | BEARISH | NEUTRAL
    status: str  # ARMED | BLOCKED

    gates: list[Gate]
    blocked_by: list[str]  # names of the gates that failed, for analytics
    blocked_reasons: list[str]  # the same failures written out for a reader
    evidence: list[Evidence]
    score: float  # 0-100, how much of this setup's ideal case is present
    grade: str  # A | B | C | D

    assumption: str
    trigger: str
    invalidation: str

    strike: float | None
    entry_reference: float | None  # underlying level the trigger keys on
    stop_reference: float | None  # underlying level that invalidates
    target_reference: float | None  # underlying level being played for
    expected_premium_points: float | None  # translated through delta, buy side only

    # Live-decision fields: armed says "conditions are right", readiness says
    # "act now, wait, or let it go".
    readiness: str  # WAIT | NOW | MISSED | NA
    distance_points: float | None  # points between spot and the level it keys on
    readiness_note: str

    historical: CalibrationRead | None
    warnings: list[str] = field(default_factory=list)
    narrative: str = ""


@dataclass
class SetupContext:
    """Everything the catalog needs, assembled once by the caller."""

    spot_price: float
    chain: pd.DataFrame
    session_candles: pd.DataFrame  # today's 5-minute bars, ascending
    structure: ms.MarketStructureSummary | None
    trend: TrendSummary | None
    regime: regime_module.RegimeSummary
    gex: gex_module.GexSummary | None
    call_walls: list[OiWall] = field(default_factory=list)
    put_walls: list[OiWall] = field(default_factory=list)
    calibration: dict[str, CalibrationRead] = field(default_factory=dict)

    @property
    def expected_move(self) -> float:
        return self.regime.implied_daily_move_points or _FALLBACK_EXPECTED_MOVE

    @property
    def proximity(self) -> float:
        return self.expected_move * _PROXIMITY_FRACTION


# ------------------------------------------------------------- utilities --


def _grade(score: float, calibration: CalibrationRead | None) -> str:
    """Letter grade from evidence score, capped when history is thin.

    The cap is the point of this function. A setup can look textbook-perfect
    on today's readings and still have never been proven on this market, and
    presenting that as an A would be exactly the kind of false confidence
    this project refuses to produce.
    """
    if score >= _GRADE_A:
        base = "A"
    elif score >= _GRADE_B:
        base = "B"
    elif score >= _GRADE_C:
        base = "C"
    else:
        base = "D"

    sample = calibration.sample_size if calibration else 0
    if sample >= _MIN_TRUSTED_SAMPLE:
        return base
    if sample >= 5:
        return {"A": "B", "B": "B", "C": "C", "D": "D"}[base]
    return {"A": "C", "B": "C", "C": "C", "D": "D"}[base]


def _sample_warning(calibration: CalibrationRead | None) -> list[str]:
    sample = calibration.sample_size if calibration else 0
    if sample >= _MIN_TRUSTED_SAMPLE:
        return []
    if sample == 0:
        return [
            "This setup has never been graded on real data yet, so its grade is capped at C no "
            "matter how good today's readings look. Treat the score as 'conditions match', not "
            "'this wins'."
        ]
    return [
        f"Only {sample} graded outcome(s) so far -- too few to trust a win rate. Grade is capped "
        "until at least 20 have accumulated."
    ]


def _delta_at(chain: pd.DataFrame, strike: float | None, option_type: str) -> float | None:
    if chain.empty or strike is None or "delta" not in chain.columns:
        return None
    row = chain[(chain["strike"] == strike) & (chain["option_type"] == option_type)]
    if row.empty or pd.isna(row.iloc[0]["delta"]):
        return None
    return abs(float(row.iloc[0]["delta"]))


def _nearest_strike(chain: pd.DataFrame, target: float) -> float | None:
    if chain.empty:
        return None
    strikes = chain["strike"].dropna().unique()
    if len(strikes) == 0:
        return None
    return float(min(strikes, key=lambda s: abs(s - target)))


def _premium_from_underlying(
    ctx: SetupContext, strike: float | None, option_type: str, underlying_points: float
) -> float | None:
    """Translate an underlying move into an approximate option premium move.

    Delta is the first-order conversion and the only one this feed supports
    honestly. It **understates** a bought option's gain on a large favourable
    move (gamma makes delta grow in your favour) and understates the loss on
    a large adverse one, so the number below is a conservative floor for
    buyers, not a forecast. Deliberately not gamma-adjusted: a second-order
    estimate built on a single chain snapshot would look more precise while
    being no more reliable.
    """
    delta = _delta_at(ctx.chain, strike, option_type)
    if delta is None:
        return None
    return round(underlying_points * delta, 1)


def _readiness(
    ctx: SetupContext, action: str, direction: str, entry_reference: float | None
) -> tuple[str, float | None, str]:
    """Where price sits relative to this setup's own level, right now.

    Separate from the armed/blocked question on purpose. A setup can be armed
    all afternoon while price sits 80 points away from the level it depends
    on -- "armed" means the conditions are right, and answering "so do I click
    now?" needs the distance, which is the number a live decision actually
    turns on and the one this engine did not previously compute.

    MISSED is not a failure state, it is a discipline one. A breakout entered
    40 points late has the same stop and a worse reward, so it is a different
    trade from the one that was scored -- naming that keeps the score honest
    rather than quietly letting a stale signal look fresh.
    """
    if entry_reference is None:
        return (
            READINESS_NA,
            None,
            "This setup has no single price level to watch -- follow its written trigger instead.",
        )

    spot = ctx.spot_price
    gap = spot - entry_reference
    distance = round(abs(gap), 1)
    chase_band = ctx.expected_move * _CHASE_FRACTION
    at_level_band = ctx.expected_move * _AT_LEVEL_FRACTION

    if action in (BUY_CE, BUY_PE):
        crossed = gap > 0 if direction == BULLISH else gap < 0
        if not crossed:
            return (
                WAIT,
                distance,
                f"NIFTY is {distance:.0f} points {'below' if direction == BULLISH else 'above'} "
                f"{entry_reference:.0f}. Nothing to do until it closes a 5-minute candle through it.",
            )
        if distance <= chase_band:
            return (
                NOW,
                distance,
                f"NIFTY has moved through {entry_reference:.0f} and is still within "
                f"{distance:.0f} points of it. This is the window -- the stop is close enough "
                "to keep the trade the size it was meant to be.",
            )
        return (
            MISSED,
            distance,
            f"NIFTY is already {distance:.0f} points past {entry_reference:.0f}. Entering here "
            "means the same stop with less reward left. Let it go and wait for the next one.",
        )

    if action in (SELL_CE, SELL_PE):
        level_is_ceiling = action == SELL_CE
        breached = gap > 0 if level_is_ceiling else gap < 0
        if breached:
            return (
                MISSED,
                distance,
                f"NIFTY is {distance:.0f} points {'above' if level_is_ceiling else 'below'} "
                f"{entry_reference:.0f}. The level this setup was selling into has already given "
                "way -- it is gone, not merely weaker.",
            )
        if distance <= at_level_band:
            return (
                NOW,
                distance,
                f"NIFTY is {distance:.0f} points from {entry_reference:.0f}. Watch for a 5-minute "
                "candle that fails to close through it, and sell that rejection -- not before it.",
            )
        return (
            WAIT,
            distance,
            f"NIFTY is {distance:.0f} points from {entry_reference:.0f}, too far away for this to "
            "be the live trade. It becomes actionable if price comes back to the level.",
        )

    return (
        READINESS_NA,
        distance,
        "This setup is judged on the session as a whole rather than on one price level -- follow "
        "its written trigger.",
    )


def _build(
    *,
    key: str,
    name: str,
    action: str,
    direction: str,
    gates: list[Gate],
    evidence: list[Evidence],
    assumption: str,
    trigger: str,
    invalidation: str,
    strike: float | None,
    entry_reference: float | None,
    stop_reference: float | None,
    target_reference: float | None,
    expected_premium_points: float | None,
    ctx: SetupContext,
    extra_warnings: list[str] | None = None,
) -> SetupSignal:
    # Gate *names* state the condition that must hold ("Market is not
    # trending"), so listing a failed gate by name reads as the opposite of
    # what happened. The detail text is written for the failing case, so
    # that is what a reader gets; the names are kept alongside purely so the
    # ledger can group failures without parsing prose.
    readiness, distance_points, readiness_note = _readiness(
        ctx, action, direction, entry_reference
    )

    failed = [g for g in gates if not g.passed]
    blocked_by = [g.name for g in failed]
    blocked_reasons = [g.detail for g in failed]
    status = BLOCKED if failed else ARMED

    total_weight = sum(e.weight for e in evidence) or 1.0
    score = round(sum(e.earned for e in evidence) / total_weight * 100, 1)

    calibration = ctx.calibration.get(key)
    warnings = list(extra_warnings or [])
    warnings.extend(_sample_warning(calibration))
    if ctx.regime.implied_daily_move_points is None:
        warnings.append(
            "No live straddle price was available, so the day's expected move is a generic "
            "fallback rather than today's actual priced move. Level distances below are rough."
        )

    side = BUY_PREMIUM if action in (BUY_CE, BUY_PE) else SELL_PREMIUM

    if status == BLOCKED:
        narrative = f"{name} is not available right now. " + " ".join(blocked_reasons)
    else:
        narrative = f"{name} is armed. {readiness_note} {assumption}"

    return SetupSignal(
        key=key,
        name=name,
        action=action,
        side=side,
        direction=direction,
        status=status,
        gates=gates,
        blocked_by=blocked_by,
        blocked_reasons=blocked_reasons,
        evidence=evidence,
        score=score,
        grade=_grade(score, calibration),
        assumption=assumption,
        trigger=trigger,
        invalidation=invalidation,
        strike=strike,
        entry_reference=entry_reference,
        stop_reference=stop_reference,
        target_reference=target_reference,
        expected_premium_points=expected_premium_points,
        readiness=readiness,
        distance_points=distance_points,
        readiness_note=readiness_note,
        historical=calibration,
        warnings=warnings,
        narrative=narrative,
    )


def _market_open(ctx: SetupContext) -> Gate:
    """Just "is the market open" -- for setups whose own timing rules already
    cover the opening window."""
    closed = ctx.regime.session_window == "CLOSED"
    return Gate(
        "Market is open",
        not closed,
        "The market is closed. This is a read on the last session, not something to act on now."
        if closed
        else "The market is open.",
    )


def _tradeable_window(ctx: SetupContext) -> Gate:
    """The market is open, and past the first thirty minutes.

    Previously each setup asked only `session_window != "OPENING"`. Once a
    CLOSED window existed that check started passing outside market hours, so
    setups would arm at six in the morning against a market that had not
    opened. Asking for the windows that *are* tradeable, rather than
    excluding the one that is not, cannot go wrong the same way when another
    window is added.
    """
    window = ctx.regime.session_window
    if window == "CLOSED":
        detail = (
            "The market is closed. This is a read on the last session's data, not something to act "
            "on until the next one opens."
        )
    elif window == "OPENING":
        detail = (
            "Still inside the first 30 minutes -- volatility is unwinding from the overnight gap "
            "and direction is unresolved."
        )
    else:
        detail = "The market is open and past the opening 30 minutes."
    return Gate("Market is open and settled", window in ("MIDDAY", "CLOSING"), detail)


def _ev(name: str, condition: bool, weight: float, yes: str, no: str) -> Evidence:
    """Binary evidence item: earns full weight or nothing, with the reading
    text chosen to explain which happened."""
    return Evidence(
        name=name,
        reading="Yes" if condition else "No",
        earned=weight if condition else 0.0,
        weight=weight,
        detail=yes if condition else no,
    )


# ----------------------------------------------------------- the catalog --


def _initial_balance_breakout(ctx: SetupContext, bullish: bool) -> SetupSignal | None:
    """Buy premium on a session extending beyond its opening range.

    The day-type research is the whole basis for this one: a session that
    extends well past its initial balance and holds near the extreme is the
    profile in which a bought option can outrun its own decay. Every gate
    below exists to keep this setup off the days that merely *look* like
    that in the first hour.
    """
    st = ctx.structure
    if st is None or st.day_type.ib_high is None or st.day_type.ib_low is None:
        return None

    ib_high, ib_low = st.day_type.ib_high, st.day_type.ib_low
    level = ib_high if bullish else ib_low
    spot = ctx.spot_price
    distance = (spot - level) if bullish else (level - spot)

    day_type = st.day_type.day_type
    structure_agrees = st.structure_trend == (ms.BULLISH if bullish else ms.BEARISH)

    gates = [
        Gate(
            "Initial balance has formed",
            True,
            "The first 30 minutes have completed, so there is a real opening range to break.",
        ),
        _tradeable_window(ctx),
        Gate(
            "Session is not a contained (non-trend) day",
            day_type != ms.NON_TREND,
            f"Day type is {day_type.replace('_', ' ').lower()}, which leaves room to extend."
            if day_type != ms.NON_TREND
            else "Today's entire range has stayed near its opening range -- a breakout here is far "
            "more likely to be a false one.",
        ),
        Gate(
            "Premium is not decisively rich",
            ctx.regime.premium_stance != regime_module.SELL_FAVORED,
            "Conditions do not argue against paying for premium today."
            if ctx.regime.premium_stance != regime_module.SELL_FAVORED
            else "Today's regime read favours selling premium, not buying it -- buying a breakout "
            "into that is fighting both decay and pricing.",
        ),
        Gate(
            "Price is at or beyond the level",
            distance >= -ctx.proximity,
            f"NIFTY is within reach of the {'upper' if bullish else 'lower'} edge of the opening "
            f"range ({level:.0f})."
            if distance >= -ctx.proximity
            else f"NIFTY is still {abs(distance):.0f} points away from {level:.0f} -- too far for "
            "this to be the live trade right now.",
        ),
    ]

    evidence = [
        _ev(
            "Day type supports extension",
            day_type in (ms.TREND, ms.NORMAL_VARIATION),
            25,
            f"Day type is {day_type.replace('_', ' ').lower()} -- the session is already extending "
            "beyond its opening range rather than rotating inside it.",
            "The session has not yet shown it can extend beyond its opening range.",
        ),
        _ev(
            "Swing structure agrees",
            structure_agrees,
            20,
            f"Swing highs and lows are {'rising' if bullish else 'falling'}, so the breakout would "
            "be continuing the existing structure rather than fighting it.",
            f"Swing structure is {st.structure_trend.lower()}, which does not support a "
            f"{'upside' if bullish else 'downside'} break.",
        ),
        _ev(
            "Movement is underpriced",
            ctx.regime.premium_pricing == regime_module.CHEAP,
            20,
            "NIFTY has been moving more than the options are pricing, so a bought option starts "
            "with the pricing in its favour.",
            f"Premium pricing is {ctx.regime.premium_pricing.lower()} -- no pricing tailwind for a buyer.",
        ),
        _ev(
            "Dealer hedging amplifies moves",
            ctx.gex is not None and ctx.gex.regime == gex_module.NEGATIVE_GAMMA,
            15,
            "Net dealer gamma is negative, so hedging flow pushes with a break instead of fading it.",
            "Dealer hedging is not currently in a mode that amplifies breakouts, so the move has to "
            "carry itself.",
        ),
        _ev(
            "Price on the right side of VWAP",
            ctx.trend is not None
            and ctx.trend.price_vs_vwap == ("ABOVE" if bullish else "BELOW"),
            10,
            f"NIFTY is trading {'above' if bullish else 'below'} the day's volume-weighted average "
            "price, which is where the session's control sits.",
            "NIFTY is on the wrong side of the day's average price for this direction.",
        ),
        _ev(
            "Trend strength present",
            ctx.trend is not None and ctx.trend.adx is not None and ctx.trend.adx >= 20,
            10,
            f"Trend-strength reading (ADX {ctx.trend.adx if ctx.trend else '?'}) shows real "
            "directional pressure rather than chop.",
            "Trend strength is weak, so a break is more likely to stall than to run.",
        ),
    ]

    option_type = "CE" if bullish else "PE"
    strike = _nearest_strike(ctx.chain, spot)
    target_points = ctx.expected_move * 0.6
    target = level + target_points if bullish else level - target_points

    return _build(
        key=f"IB_BREAKOUT_{'LONG' if bullish else 'SHORT'}",
        name=f"Opening-range breakout ({'up' if bullish else 'down'})",
        action=BUY_CE if bullish else BUY_PE,
        direction=BULLISH if bullish else BEARISH,
        gates=gates,
        evidence=evidence,
        assumption=(
            f"The assumption is that today keeps extending {'higher' if bullish else 'lower'} after "
            f"leaving its opening range, instead of snapping back inside it. If today turns out to be "
            "a rotation day, this setup is simply wrong and the stop below is what proves it."
        ),
        trigger=(
            f"a completed 5-minute candle closes {'above' if bullish else 'below'} {level:.0f} "
            f"(the {'high' if bullish else 'low'} of the first 30 minutes), with the next candle not "
            "immediately reversing back through it."
        ),
        invalidation=(
            f"NIFTY closes a 5-minute candle back {'below' if bullish else 'above'} {level:.0f}. "
            "That is a failed break, and failed breaks reverse hard."
        ),
        strike=strike,
        entry_reference=level,
        stop_reference=level,
        target_reference=round(target, 1),
        expected_premium_points=_premium_from_underlying(ctx, strike, option_type, target_points),
        ctx=ctx,
    )


def _initial_balance_failure(ctx: SetupContext, bullish: bool) -> SetupSignal | None:
    """Sell premium after a failed break of the opening range.

    `bullish` here describes the resulting view on the underlying: a failed
    break *below* the opening range is a bullish failure, and the trade is
    selling puts into it.
    """
    st = ctx.structure
    if st is None or st.day_type.ib_high is None or st.day_type.ib_low is None:
        return None

    ib_high, ib_low = st.day_type.ib_high, st.day_type.ib_low
    session_high = st.day_type.session_high
    session_low = st.day_type.session_low
    if session_high is None or session_low is None:
        return None

    # A failure is: the session poked past the edge, but price is now back inside.
    poked = (session_low < ib_low) if bullish else (session_high > ib_high)
    back_inside = ib_low <= ctx.spot_price <= ib_high
    day_type = st.day_type.day_type

    gates = [
        Gate(
            "A break was attempted and failed",
            poked and back_inside,
            f"Price traded {'below' if bullish else 'above'} the opening range and has come back "
            "inside it -- the definition of a failed break."
            if poked and back_inside
            else "No failed break to fade: price has either not tested the edge or has not returned "
            "inside the opening range.",
        ),
        Gate(
            "Session is not trending",
            day_type != ms.TREND,
            "The session is not showing a trend-day profile, so fading an extreme is reasonable."
            if day_type != ms.TREND
            else "This is behaving like a trend day -- fading extremes on a trend day is how sellers "
            "get run over.",
        ),
        Gate(
            "Premium is not decisively cheap",
            ctx.regime.premium_stance != regime_module.BUY_FAVORED,
            "Conditions do not argue against selling premium today."
            if ctx.regime.premium_stance != regime_module.BUY_FAVORED
            else "Today's regime read favours buying premium -- selling into that is taking the "
            "wrong side of the pricing.",
        ),
        Gate(
            "Not the closing window on expiry day",
            not (ctx.regime.is_expiry_day and ctx.regime.session_window == "CLOSING"),
            "Outside the highest-gamma window of the week."
            if not (ctx.regime.is_expiry_day and ctx.regime.session_window == "CLOSING")
            else "Final hours of expiry day -- the single most dangerous window for a premium "
            "seller. This setup stays off.",
        ),
        _market_open(ctx),
    ]

    opposing_wall = ctx.put_walls if bullish else ctx.call_walls
    fresh_wall = next((w for w in opposing_wall if w.freshness == "FRESH"), None)

    evidence = [
        _ev(
            "Contained day profile",
            day_type in (ms.NON_TREND, ms.NEUTRAL, ms.NORMAL_VARIATION),
            25,
            f"Day type is {day_type.replace('_', ' ').lower()} -- a rotational profile, which is what "
            "this setup needs.",
            "Day profile does not yet confirm rotation.",
        ),
        _ev(
            "Premium is richly priced",
            ctx.regime.premium_pricing == regime_module.RICH,
            25,
            "Options are pricing more movement than NIFTY has actually been delivering, which is the "
            "seller's edge.",
            f"Premium pricing is {ctx.regime.premium_pricing.lower()} -- no pricing tailwind for a seller.",
        ),
        _ev(
            "Dealer hedging damps moves",
            ctx.gex is not None and ctx.gex.regime == gex_module.POSITIVE_GAMMA,
            20,
            "Net dealer gamma is positive, so hedging flow leans against continuation -- exactly the "
            "condition in which a failed break stays failed.",
            "Dealer hedging is not currently damping moves, so the failure may not hold.",
        ),
        _ev(
            "Fresh open interest defending the side sold",
            fresh_wall is not None,
            20,
            f"There is freshly-built open interest at {fresh_wall.strike:.0f} on the "
            f"{'put' if bullish else 'call'} side -- new positioning defending that level today, not "
            "a stale level left over from last week."
            if fresh_wall
            else "",
            "No freshly-built open interest is defending this side, so the level has less support "
            "than the setup would like.",
        ),
        _ev(
            "No unwinding warning on that wall",
            fresh_wall is not None and not fresh_wall.unwinding_warning,
            10,
            "Open interest at that level is being added to, not aggressively unwound.",
            "Either there is no wall to lean on, or the one that exists is being unwound on heavy "
            "volume -- a specific warning that it is about to break.",
        ),
    ]

    option_type = "PE" if bullish else "CE"
    reference_level = ib_low if bullish else ib_high
    strike = _nearest_strike(ctx.chain, reference_level)

    return _build(
        key=f"IB_FAILURE_FADE_{'LONG' if bullish else 'SHORT'}",
        name=f"Failed opening-range break ({'downside' if bullish else 'upside'} rejection)",
        action=SELL_PE if bullish else SELL_CE,
        direction=BULLISH if bullish else BEARISH,
        gates=gates,
        evidence=evidence,
        assumption=(
            f"The assumption is that today's push {'below' if bullish else 'above'} the opening range "
            "was a liquidity grab that has already failed, and price stays inside the range for the "
            "rest of the session. If the level breaks again with conviction, the assumption is dead."
        ),
        trigger=(
            f"NIFTY holds inside the opening range ({ib_low:.0f} to {ib_high:.0f}) for two completed "
            f"5-minute candles after the failed break, then sell the {option_type} at {strike:.0f}."
            if strike
            else "NIFTY holds inside the opening range for two completed 5-minute candles."
        ),
        invalidation=(
            f"a 5-minute candle closes {'below' if bullish else 'above'} {reference_level:.0f} again. "
            "A second break after a failure is usually the real one."
        ),
        strike=strike,
        entry_reference=ctx.spot_price,
        stop_reference=reference_level,
        target_reference=(ib_high + ib_low) / 2,
        expected_premium_points=None,
        ctx=ctx,
    )


def _wall_fade(ctx: SetupContext, call_side: bool) -> SetupSignal | None:
    """Sell premium into a fresh, heavy open-interest wall in a damped regime.

    This is the setup the OI research most directly supports, and the
    freshness/unwinding filters are exactly what it warned raw "top OI
    strikes" was missing.
    """
    walls = ctx.call_walls if call_side else ctx.put_walls
    if not walls:
        return None

    wall = walls[0]
    spot = ctx.spot_price
    distance = (wall.strike - spot) if call_side else (spot - wall.strike)

    gates = [
        Gate(
            "Wall sits the right side of price",
            distance > 0,
            f"The {'call' if call_side else 'put'} wall at {wall.strike:.0f} is "
            f"{'above' if call_side else 'below'} spot, so it can act as "
            f"{'resistance' if call_side else 'support'}."
            if distance > 0
            else f"The heaviest {'call' if call_side else 'put'} open interest is already behind "
            "price, so there is no level left to fade into.",
        ),
        Gate(
            "Price is close enough to matter",
            0 < distance <= ctx.proximity * 2,
            f"NIFTY is {distance:.0f} points from the level -- close enough for it to be the "
            "operative level today."
            if 0 < distance <= ctx.proximity * 2
            else f"The level is {abs(distance):.0f} points away, too far to be today's trade.",
        ),
        Gate(
            "Wall is not being unwound",
            not wall.unwinding_warning,
            "Open interest at that strike is holding or growing."
            if not wall.unwinding_warning
            else "Heavy volume with falling open interest at that strike -- positions are being "
            "closed out and the level is likely about to break. Do not sell into it.",
        ),
        Gate(
            "Regime is not trending against the fade",
            ctx.regime.structure_regime != regime_module.TRENDING,
            "The market is not in a clean trend, so a level has a real chance of holding."
            if ctx.regime.structure_regime != regime_module.TRENDING
            else "The market is trending. Trending markets go through open-interest walls, and the "
            "research is explicit that pinning logic is least reliable exactly here.",
        ),
        Gate(
            "Not the closing window on expiry day",
            not (ctx.regime.is_expiry_day and ctx.regime.session_window == "CLOSING"),
            "Outside the highest-gamma window of the week."
            if not (ctx.regime.is_expiry_day and ctx.regime.session_window == "CLOSING")
            else "Final hours of expiry day -- highest gamma of the week. This setup stays off.",
        ),
        _market_open(ctx),
    ]

    gamma_wall = (
        ctx.gex.call_wall_strike if (ctx.gex and call_side) else (ctx.gex.put_wall_strike if ctx.gex else None)
    )

    evidence = [
        _ev(
            "Wall is freshly built today",
            wall.freshness == "FRESH",
            30,
            f"Open interest at {wall.strike:.0f} was built up today rather than sitting there from "
            "previous sessions -- fresh positioning is conviction, stale positioning is furniture.",
            "This level's open interest is stale -- it has been sitting there rather than being "
            "added to today, so it carries less weight.",
        ),
        _ev(
            "Gamma agrees with the level",
            gamma_wall is not None and abs(gamma_wall - wall.strike) <= 100,
            20,
            f"The heaviest dealer-hedging weight sits at {gamma_wall:.0f}, essentially the same level "
            "-- open interest and hedging pressure point at the same place."
            if gamma_wall
            else "",
            "Dealer hedging weight is concentrated somewhere other than this strike, so the level is "
            "supported by open interest alone.",
        ),
        _ev(
            "Dealer hedging damps moves",
            ctx.gex is not None and ctx.gex.regime == gex_module.POSITIVE_GAMMA,
            20,
            "Net positive dealer gamma means hedging flow actively pushes back against approaches to "
            "this level.",
            "Dealer hedging is not damping moves right now, so the level has to hold on its own.",
        ),
        _ev(
            "Premium is richly priced",
            ctx.regime.premium_pricing == regime_module.RICH,
            20,
            "Options price more movement than NIFTY has been delivering, so the seller starts ahead.",
            f"Premium pricing is {ctx.regime.premium_pricing.lower()} -- no pricing tailwind.",
        ),
        _ev(
            "Session profile is contained",
            ctx.regime.day_type in (ms.NON_TREND, ms.NEUTRAL),
            10,
            "Today's range has stayed contained, which is the profile in which levels hold.",
            "Today's profile does not confirm containment.",
        ),
    ]

    option_type = "CE" if call_side else "PE"

    return _build(
        key=f"WALL_FADE_{'CALL' if call_side else 'PUT'}",
        name=f"Fade the {'call' if call_side else 'put'} wall at {wall.strike:.0f}",
        action=SELL_CE if call_side else SELL_PE,
        direction=BEARISH if call_side else BULLISH,
        gates=gates,
        evidence=evidence,
        assumption=(
            f"The assumption is that {wall.strike:.0f} holds as "
            f"{'resistance' if call_side else 'support'} for the rest of the session, because the "
            "people who wrote that open interest today will defend it and dealer hedging leans the "
            "same way. If NIFTY closes through it, that assumption is gone -- not weakened, gone."
        ),
        trigger=(
            f"NIFTY approaches {wall.strike:.0f} and a 5-minute candle fails to close beyond it. Sell "
            f"the {wall.strike:.0f} {option_type} on that rejection, not in anticipation of it."
        ),
        invalidation=(
            f"any 5-minute candle closes {'above' if call_side else 'below'} {wall.strike:.0f}, or "
            "the open interest at that strike starts falling on heavy volume during the session."
        ),
        strike=wall.strike,
        entry_reference=wall.strike,
        stop_reference=wall.strike,
        target_reference=None,
        expected_premium_points=None,
        ctx=ctx,
    )


def _trend_pullback(ctx: SetupContext, bullish: bool) -> SetupSignal | None:
    """Buy premium on a pullback inside an established trend.

    The only buy-side setup here that does not need a breakout: it waits for
    the market to come back to the day's average price in a trend that has
    already broken structure in that direction.
    """
    st = ctx.structure
    if st is None or ctx.trend is None or ctx.trend.vwap is None:
        return None

    vwap = ctx.trend.vwap
    spot = ctx.spot_price
    distance_to_vwap = abs(spot - vwap)
    structure_agrees = st.structure_trend == (ms.BULLISH if bullish else ms.BEARISH)
    bos_agrees = (
        st.last_bos is not None
        and st.last_bos.direction == (ms.BULLISH if bullish else ms.BEARISH)
    )

    gates = [
        Gate(
            "Market is trending",
            ctx.regime.structure_regime == regime_module.TRENDING,
            "The regime read says trending, which is the only condition in which buying a pullback "
            "makes sense."
            if ctx.regime.structure_regime == regime_module.TRENDING
            else f"Regime is {ctx.regime.structure_regime.lower()}, not trending. In a range, a "
            "pullback is just the other half of the rotation.",
        ),
        Gate(
            "Structure agrees with the direction",
            structure_agrees,
            f"Swing structure is {'bullish' if bullish else 'bearish'}, matching the direction traded."
            if structure_agrees
            else f"Swing structure is {st.structure_trend.lower()}, which contradicts this direction.",
        ),
        Gate(
            "Price has actually pulled back",
            distance_to_vwap <= ctx.proximity,
            f"NIFTY is {distance_to_vwap:.0f} points from the day's average price -- a genuine "
            "pullback rather than a chase."
            if distance_to_vwap <= ctx.proximity
            else f"NIFTY is {distance_to_vwap:.0f} points from the day's average price. Entering here "
            "is chasing, not buying a pullback.",
        ),
        _tradeable_window(ctx),
    ]

    evidence = [
        _ev(
            "Structure has broken in this direction",
            bos_agrees,
            25,
            "The last structural break was in this direction, so the trend has been confirmed by "
            "price rather than only by indicators.",
            "No recent structural break confirms this direction.",
        ),
        _ev(
            "Trend strength is real",
            ctx.trend.adx is not None and ctx.trend.adx >= 25,
            20,
            f"Trend strength (ADX {ctx.trend.adx}) is above the level that separates a trend from chop.",
            "Trend strength is below the threshold that distinguishes a trend from noise.",
        ),
        _ev(
            "Day type supports continuation",
            ctx.regime.day_type in (ms.TREND, ms.NORMAL_VARIATION),
            20,
            f"Day type is {ctx.regime.day_type.replace('_', ' ').lower()}, consistent with a session "
            "that keeps going.",
            "Day profile does not support continuation.",
        ),
        _ev(
            "Movement is underpriced",
            ctx.regime.premium_pricing == regime_module.CHEAP,
            20,
            "Options are pricing less movement than NIFTY has delivered, so the buyer starts ahead.",
            f"Premium pricing is {ctx.regime.premium_pricing.lower()} -- the buyer is paying up.",
        ),
        _ev(
            "Moving averages aligned",
            ctx.trend.ma_crossover == (ms.BULLISH if bullish else ms.BEARISH),
            15,
            "Short and long moving averages are stacked in this direction.",
            "Moving averages are not aligned with this direction.",
        ),
    ]

    option_type = "CE" if bullish else "PE"
    strike = _nearest_strike(ctx.chain, spot)
    target_points = ctx.expected_move * 0.5
    target = spot + target_points if bullish else spot - target_points

    return _build(
        key=f"TREND_PULLBACK_{'LONG' if bullish else 'SHORT'}",
        name=f"Trend pullback to average price ({'long' if bullish else 'short'})",
        action=BUY_CE if bullish else BUY_PE,
        direction=BULLISH if bullish else BEARISH,
        gates=gates,
        evidence=evidence,
        assumption=(
            f"The assumption is that this is a pause inside a {'rising' if bullish else 'falling'} "
            "market, not the end of it. The day's average price is where that assumption gets tested: "
            "trends resume from it, reversals close through it."
        ),
        trigger=(
            f"NIFTY tests the day's average price ({vwap:.0f}) and a 5-minute candle closes back "
            f"{'above' if bullish else 'below'} it. Buy the {strike:.0f} {option_type} on that close."
            if strike
            else f"NIFTY tests {vwap:.0f} and closes back {'above' if bullish else 'below'} it."
        ),
        invalidation=(
            f"a 5-minute candle closes {'below' if bullish else 'above'} {vwap:.0f} and the next one "
            "does not recover it. At that point the trend is no longer in control of the session."
        ),
        strike=strike,
        entry_reference=vwap,
        stop_reference=vwap,
        target_reference=round(target, 1),
        expected_premium_points=_premium_from_underlying(ctx, strike, option_type, target_points),
        ctx=ctx,
    )


def _range_short_straddle(ctx: SetupContext) -> SetupSignal | None:
    """Sell both sides in a contained, richly-priced, damped session.

    This is the same economic trade as the existing HLC rule, but gated on
    the regime instead of assuming it. The HLC rule sells whenever the
    previous session's closes look a certain way; this one refuses to sell
    unless today is actually behaving like a range day. That difference is
    the point -- the domain research flagged precisely this: the HLC plan is
    a range-day strategy by construction with nothing checking whether it is
    a range day.
    """
    atm = ctx.regime.atm_strike
    if atm is None:
        return None

    gates = [
        Gate(
            "Market is not trending",
            ctx.regime.structure_regime != regime_module.TRENDING,
            "The regime read is not trending, so a contained session is plausible."
            if ctx.regime.structure_regime != regime_module.TRENDING
            else "The market is trending. Selling both sides into a trend is the fastest way to lose "
            "more than the premium collected.",
        ),
        Gate(
            "Premium is not cheap",
            ctx.regime.premium_pricing != regime_module.CHEAP,
            "Options are not underpriced relative to real movement."
            if ctx.regime.premium_pricing != regime_module.CHEAP
            else "NIFTY has been moving more than options are pricing. Selling into that is selling "
            "movement for less than it has been costing.",
        ),
        _tradeable_window(ctx),
        Gate(
            "Not the closing window on expiry day",
            not (ctx.regime.is_expiry_day and ctx.regime.session_window == "CLOSING"),
            "Outside the week's highest-gamma window."
            if not (ctx.regime.is_expiry_day and ctx.regime.session_window == "CLOSING")
            else "Final hours of expiry day. Gamma here can move an option's sensitivity faster than "
            "any stop can react.",
        ),
        Gate(
            "Dealer hedging is not amplifying moves",
            ctx.gex is None or ctx.gex.regime != gex_module.NEGATIVE_GAMMA,
            "Hedging flow is not in the mode that accelerates moves."
            if (ctx.gex is None or ctx.gex.regime != gex_module.NEGATIVE_GAMMA)
            else "Net dealer gamma is negative -- hedging pushes with moves today, which is the exact "
            "condition that turns a quiet range into a fast one.",
        ),
    ]

    evidence = [
        _ev(
            "Premium is richly priced",
            ctx.regime.premium_pricing == regime_module.RICH,
            30,
            "Options price more movement than NIFTY has been delivering. This is the entire economic "
            "basis for selling.",
            "Premium is only fairly priced, so the trade rests on the range holding rather than on "
            "any pricing edge.",
        ),
        _ev(
            "Contained day profile",
            ctx.regime.day_type in (ms.NON_TREND, ms.NEUTRAL),
            25,
            f"Day type is {ctx.regime.day_type.replace('_', ' ').lower()} -- the session is rotating, "
            "not going anywhere.",
            "The session has not confirmed a contained profile.",
        ),
        _ev(
            "Dealer hedging damps moves",
            ctx.gex is not None and ctx.gex.regime == gex_module.POSITIVE_GAMMA,
            20,
            "Positive net dealer gamma actively pushes back against moves in either direction -- the "
            "mechanism that keeps a sold straddle safe.",
            "Dealer hedging is not damping moves, so nothing structural is holding the range together.",
        ),
        _ev(
            "Volatility is priced high",
            ctx.regime.iv_percentile is not None and ctx.regime.iv_percentile >= 60,
            15,
            f"Implied volatility is at the {ctx.regime.iv_percentile:.0f}th percentile of its own "
            "recent range -- selling near the top of that range."
            if ctx.regime.iv_percentile is not None
            else "",
            "Volatility is not elevated within its own recent range, so there is less to collect.",
        ),
        _ev(
            "Time decay window",
            ctx.regime.session_window == "CLOSING" and not ctx.regime.is_expiry_day,
            10,
            "Final stretch of a non-expiry session -- decay accelerates here while gamma risk is "
            "still manageable.",
            "Not in the fastest-decay window of the session.",
        ),
    ]

    expected = ctx.regime.implied_daily_move_points

    return _build(
        key="RANGE_SHORT_STRADDLE",
        name="Sell both sides into a contained session",
        action=SELL_STRADDLE,
        direction=NEUTRAL,
        gates=gates,
        evidence=evidence,
        assumption=(
            f"The assumption is that NIFTY stays inside roughly "
            f"{(ctx.spot_price - (expected or 0)):.0f} to {(ctx.spot_price + (expected or 0)):.0f} "
            "for the rest of the session -- the move the options themselves are pricing. This trade "
            "makes money from time passing, and loses if NIFTY picks a direction and commits to it."
        ),
        trigger=(
            f"NIFTY has held inside its opening range for at least an hour, then sell the {atm:.0f} "
            "call and put together. Do not leg in one side at a time -- half a straddle is a "
            "directional bet you did not intend to make."
        ),
        invalidation=(
            "either side's premium rises past the high of the previous completed 5-minute candle, or "
            "NIFTY breaks its opening range with a 5-minute close. Exit both legs, not just the "
            "losing one."
        ),
        strike=atm,
        entry_reference=ctx.spot_price,
        stop_reference=None,
        target_reference=None,
        expected_premium_points=None,
        ctx=ctx,
        extra_warnings=(
            [
                "Selling both sides has open-ended risk on a fast move. The stop rule above is the "
                "only thing bounding it, and on a gap or a news move it can be jumped straight past."
            ]
        ),
    )


def _expiry_pin_fade(ctx: SetupContext) -> SetupSignal | None:
    """Sell premium toward the heaviest-gamma strike on expiry day.

    Framed as hedging-flow concentration, never as "price will go to max
    pain" -- the research is explicit that the max-pain framing overstates
    the evidence and that the credible mechanism is dealer gamma hedging,
    which is what this keys on.
    """
    if ctx.gex is None or ctx.gex.largest_gamma_strike is None:
        return None

    pin = ctx.gex.largest_gamma_strike
    spot = ctx.spot_price
    distance = abs(spot - pin)
    above_pin = spot > pin

    gates = [
        Gate(
            "It is expiry day",
            ctx.regime.is_expiry_day,
            "Today is the expiry session, when hedging flow concentrates hardest around one strike."
            if ctx.regime.is_expiry_day
            else "Not an expiry session -- pinning behaviour is far weaker with time left on the clock.",
        ),
        Gate(
            "Dealer hedging is damping moves",
            ctx.gex.regime == gex_module.POSITIVE_GAMMA,
            "Net positive dealer gamma -- the condition under which pinning actually happens."
            if ctx.gex.regime == gex_module.POSITIVE_GAMMA
            else "Net dealer gamma is negative. Under negative gamma, hedging pushes price away from "
            "levels rather than toward them, and pinning logic is at its least reliable.",
        ),
        Gate(
            "Price is near the pin, not far from it",
            0 < distance <= ctx.proximity * 2,
            f"NIFTY is {distance:.0f} points from {pin:.0f} -- close enough for hedging flow to hold it."
            if 0 < distance <= ctx.proximity * 2
            else f"NIFTY is {distance:.0f} points from {pin:.0f}, too far for hedging flow to pull it "
            "back in the time remaining.",
        ),
        _market_open(ctx),
        Gate(
            "Not the final closing window",
            ctx.regime.session_window != "CLOSING",
            "Enough time left that decay works before gamma bites."
            if ctx.regime.session_window != "CLOSING"
            else "Final hours of expiry day -- the highest-gamma window there is. Whatever the pin "
            "says, this is not the window to sell into it.",
        ),
    ]

    evidence = [
        _ev(
            "Hedging weight is concentrated",
            ctx.gex.gamma_flip_strike is not None and abs(ctx.gex.gamma_flip_strike - pin) <= 150,
            30,
            "The point where dealer hedging changes sign sits close to the heaviest-gamma strike, so "
            "flow is concentrated rather than spread out.",
            "Hedging weight is spread across strikes rather than concentrated at one, which weakens "
            "any pinning effect.",
        ),
        _ev(
            "Session is contained",
            ctx.regime.day_type in (ms.NON_TREND, ms.NEUTRAL),
            25,
            "Today's range is contained, which is the only condition in which pinning has been "
            "observed to work.",
            "The session is not contained. Pinning does not survive a directional expiry day.",
        ),
        _ev(
            "Premium is richly priced",
            ctx.regime.premium_pricing == regime_module.RICH,
            25,
            "Options price more movement than NIFTY has been delivering.",
            f"Premium pricing is {ctx.regime.premium_pricing.lower()}.",
        ),
        _ev(
            "Market is not trending",
            ctx.regime.structure_regime == regime_module.RANGING,
            20,
            "The regime read is ranging, which is where the research says this behaviour lives.",
            "The regime is not clearly ranging, so this is a weaker case.",
        ),
    ]

    option_type = "CE" if above_pin else "PE"
    strike = _nearest_strike(ctx.chain, pin)

    return _build(
        key="EXPIRY_PIN_FADE",
        name=f"Expiry hedging-flow fade toward {pin:.0f}",
        action=SELL_CE if above_pin else SELL_PE,
        direction=BEARISH if above_pin else BULLISH,
        gates=gates,
        evidence=evidence,
        assumption=(
            f"The assumption is that dealer hedging keeps NIFTY near {pin:.0f} into the close, so an "
            f"option struck {'above' if above_pin else 'below'} it expires worthless. This is a "
            "tendency under positive gamma, not a rule -- it fails outright on a directional expiry "
            "day, and it fails fast."
        ),
        trigger=(
            f"NIFTY stalls within about {ctx.proximity:.0f} points of {pin:.0f} without closing "
            f"through it, then sell the {strike:.0f} {option_type}."
            if strike
            else f"NIFTY stalls near {pin:.0f} without closing through it."
        ),
        invalidation=(
            f"NIFTY closes a 5-minute candle decisively away from {pin:.0f}, or net dealer gamma "
            "turns negative during the session. Either one removes the mechanism this whole setup "
            "depends on."
        ),
        strike=strike,
        entry_reference=pin,
        stop_reference=None,
        target_reference=pin,
        expected_premium_points=None,
        ctx=ctx,
        extra_warnings=[
            "Expiry-day selling carries the highest gamma risk of the week. Size this smaller than "
            "any other setup here, and honour the invalidation immediately -- there is no time left "
            "for a losing expiry-day position to recover."
        ],
    )


# ------------------------------------------------------------ evaluation --


def evaluate(ctx: SetupContext) -> list[SetupSignal]:
    """Run the whole catalog. Returns every setup that could be constructed,
    armed or blocked, sorted best-first among the armed ones.

    Blocked setups are returned rather than dropped on purpose: knowing *why*
    a setup is unavailable today is as useful as knowing which one is live,
    and hiding them would make the engine look like it had no opinion when
    in fact it had a reasoned negative one.
    """
    candidates = [
        _initial_balance_breakout(ctx, bullish=True),
        _initial_balance_breakout(ctx, bullish=False),
        _initial_balance_failure(ctx, bullish=True),
        _initial_balance_failure(ctx, bullish=False),
        _wall_fade(ctx, call_side=True),
        _wall_fade(ctx, call_side=False),
        _trend_pullback(ctx, bullish=True),
        _trend_pullback(ctx, bullish=False),
        _range_short_straddle(ctx),
        _expiry_pin_fade(ctx),
    ]
    signals = [s for s in candidates if s is not None]

    # Ordered the way a live decision is made: what can be acted on this
    # minute first, then what is worth watching, then the rest. Grade breaks
    # ties within a readiness band rather than across them -- a grade-A setup
    # whose level is 80 points away is not more useful right now than a
    # grade-B one that price is sitting on.
    readiness_order = {NOW: 0, WAIT: 1, READINESS_NA: 2, MISSED: 3}
    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    signals.sort(
        key=lambda s: (
            s.status != ARMED,
            readiness_order.get(s.readiness, 4),
            grade_order[s.grade],
            -s.score,
        )
    )
    return signals


def best_setup(signals: list[SetupSignal], min_score: float = _GRADE_C) -> SetupSignal | None:
    """The single setup worth acting on, or None.

    Returning None is a real answer and the common one. A day with no armed
    setup above the score floor is a day to do nothing, and this function
    says that rather than handing back the least-bad option.

    Setups whose price has already run past the level are excluded outright.
    They still appear in the full list, because knowing a move was missed is
    useful, but presenting one as "today's best setup" would invite exactly
    the late entry the readiness check exists to prevent.
    """
    armed = [
        s
        for s in signals
        if s.status == ARMED and s.score >= min_score and s.readiness != MISSED
    ]
    return armed[0] if armed else None

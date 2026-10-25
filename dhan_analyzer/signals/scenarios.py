"""Three ways today can go, weighted by evidence that already exists, plus
the checklist that decides whether any of them is worth acting on.

## Why not one prediction

The rest of the engine answers "what is the trade". This answers the question
a trader actually holds in their head: *what are the ways this session can
unfold, and which one does the evidence lean toward.* Price can only do three
things from here -- take out the level above, take out the level below, or
stay between them -- so those are the three scenarios, always, with real
levels attached.

## The number on each scenario is not a probability

It is the **share of today's evidence** pointing that way: each factor below
carries a fixed weight, votes for exactly one scenario, and the shares are
those weights divided by the weight actually assigned. Two consequences worth
being explicit about, because a percentage on a trading screen invites being
read as a probability and this one is not:

- It says nothing about how often that scenario has come true historically.
  Nothing here is fitted to outcomes.
- A 60% share means "most of what I can measure points here", not "this
  happens 6 times in 10".

The mocked-up version of this page carried "62% / 24% / 14%" as static text.
Replacing invented probabilities with different invented probabilities would
have been the easy read of "make it real"; an evidence share is the honest
one, and it is labelled as such everywhere it appears.

## The checklist is the gate, not the scenarios

Scenarios describe the market. The checklist decides whether *you* act, and it
is deliberately separate: a beautifully-weighted upside scenario with no entry
trigger available and the market shut is still not a trade.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dhan_analyzer.signals import gex as gex_module
from dhan_analyzer.signals import market_structure as ms
from dhan_analyzer.signals import regime as regime_module
from dhan_analyzer.signals import setups as setups_module

UPSIDE, RANGE, DOWNSIDE = "UPSIDE", "RANGE", "DOWNSIDE"
TRADE, WAIT, STAND_DOWN = "TRADE", "WAIT", "STAND_DOWN"

# Factor weights. Same ordering logic as regime.py: the measures that describe
# what price has actually been doing outrank the ones that describe how it is
# being priced. They sum to 100 so a share reads directly as a percentage of
# what could be measured.
_W_STRUCTURE = 20.0
_W_TIMEFRAMES = 15.0
_W_DAY_TYPE = 15.0
_W_GAMMA = 15.0
_W_PRICING = 15.0
_W_VWAP = 10.0
_W_ADX = 10.0

# How far beyond the trigger a scenario plays for, as a fraction of the day's
# priced move. Same 0.6 the breakout setup uses, for the same reason: a target
# at the full expected move assumes the move starts from here rather than from
# the level it has to break first.
_TARGET_FRACTION = 0.6


@dataclass(frozen=True)
class ScenarioEvidence:
    factor: str
    reading: str
    weight: float
    detail: str


@dataclass(frozen=True)
class Scenario:
    key: str  # UPSIDE | RANGE | DOWNSIDE
    name: str
    direction: str  # BULLISH | BEARISH | NEUTRAL
    evidence_share: float  # 0-100 -- share of measurable evidence, NOT a probability
    trigger_level: float | None
    trigger: str
    invalidation: str
    target_level: float | None
    what_it_means: str
    evidence: list[ScenarioEvidence] = field(default_factory=list)
    matching_setups: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChecklistItem:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ScenarioSet:
    spot_price: float
    scenarios: list[Scenario]
    checklist: list[ChecklistItem]
    checklist_passed: int
    checklist_total: int
    verdict: str  # TRADE | WAIT | STAND_DOWN
    verdict_note: str
    caveat: str


# ------------------------------------------------------------- evidence --


def _vote(
    factor: str, reading: str, target: str | None, weight: float, detail: str
) -> tuple[str | None, ScenarioEvidence]:
    return target, ScenarioEvidence(factor, reading, weight, detail)


def _collect_votes(
    summary: regime_module.RegimeSummary,
    structure: ms.MarketStructureSummary | None,
    trend,
    gex_summary: gex_module.GexSummary | None,
) -> list[tuple[str | None, ScenarioEvidence]]:
    """Each factor votes for exactly one scenario, or abstains.

    Abstaining is a real outcome and is shown: a factor that could not be read
    contributes to no scenario and is excluded from the denominator, so the
    shares stay honest about how much was actually measurable rather than
    quietly treating "unknown" as "range".
    """
    votes: list[tuple[str | None, ScenarioEvidence]] = []

    # 1. Swing structure -- what price has actually been doing.
    trend_label = structure.structure_trend if structure else ms.UNCLEAR
    if trend_label == ms.BULLISH:
        votes.append(_vote("Swing structure", "Bullish", UPSIDE, _W_STRUCTURE,
                           "Higher highs and higher lows -- price is making upward progress."))
    elif trend_label == ms.BEARISH:
        votes.append(_vote("Swing structure", "Bearish", DOWNSIDE, _W_STRUCTURE,
                           "Lower highs and lower lows -- price is making downward progress."))
    else:
        votes.append(_vote("Swing structure", "No clear trend", RANGE, _W_STRUCTURE,
                           "Swings are not stacking in either direction, which is what rotation "
                           "looks like."))

    # 2. Higher-timeframe agreement.
    frames = [tf for tf in (structure.timeframes if structure else []) if tf.enough_data]
    higher = [tf for tf in frames if tf.label in ("1D", "1H", "15M")]
    if not higher:
        votes.append(_vote("Higher timeframes", "Not enough history", None, _W_TIMEFRAMES,
                           "Not enough stored bars on the higher timeframes to read them yet."))
    else:
        directions = {tf.trend for tf in higher}
        labels = ", ".join(tf.label for tf in higher)
        if directions == {ms.BULLISH}:
            votes.append(_vote("Higher timeframes", "All bullish", UPSIDE, _W_TIMEFRAMES,
                               f"{labels} all point up, so an upside break would be with them."))
        elif directions == {ms.BEARISH}:
            votes.append(_vote("Higher timeframes", "All bearish", DOWNSIDE, _W_TIMEFRAMES,
                               f"{labels} all point down, so a downside break would be with them."))
        else:
            votes.append(_vote("Higher timeframes", "Disagreeing", RANGE, _W_TIMEFRAMES,
                               f"{labels} do not agree, which usually means price is between "
                               "levels rather than travelling."))

    # 3. Day type -- a direct observation of today, not an indicator.
    day_type = summary.day_type
    if day_type == ms.TREND:
        target = UPSIDE if trend_label == ms.BULLISH else DOWNSIDE if trend_label == ms.BEARISH else None
        votes.append(_vote("Day type", "Trend day", target, _W_DAY_TYPE,
                           "Today has extended well beyond its opening range and held there."))
    elif day_type == ms.NON_TREND:
        votes.append(_vote("Day type", "Contained day", RANGE, _W_DAY_TYPE,
                           "Today's whole range has stayed close to its opening range."))
    else:
        votes.append(_vote("Day type", day_type.replace("_", " ").title(), None, _W_DAY_TYPE,
                           "The session has not committed to a profile yet."))

    # 4. Dealer gamma -- does hedging flow damp moves or push them along.
    gamma = gex_summary.regime if gex_summary else gex_module.GAMMA_UNKNOWN
    if gamma == gex_module.POSITIVE_GAMMA:
        votes.append(_vote("Dealer gamma", "Positive", RANGE, _W_GAMMA,
                           "Hedging flow leans against moves -- rallies get sold, dips get bought."))
    elif gamma == gex_module.NEGATIVE_GAMMA:
        target = UPSIDE if trend_label == ms.BULLISH else DOWNSIDE if trend_label == ms.BEARISH else None
        votes.append(_vote("Dealer gamma", "Negative", target, _W_GAMMA,
                           "Hedging flow pushes with moves, so a break tends to extend rather "
                           "than stall."))
    else:
        votes.append(_vote("Dealer gamma", "Unknown", None, _W_GAMMA,
                           "No gamma data in this chain snapshot."))

    # 5. What options are charging for movement.
    pricing = summary.premium_pricing
    if pricing == regime_module.RICH:
        votes.append(_vote("Option pricing", "Rich", RANGE, _W_PRICING,
                           "Options price more movement than NIFTY has been delivering, which is "
                           "what a contained session looks like from the pricing side."))
    elif pricing == regime_module.CHEAP:
        target = UPSIDE if trend_label == ms.BULLISH else DOWNSIDE if trend_label == ms.BEARISH else None
        votes.append(_vote("Option pricing", "Cheap", target, _W_PRICING,
                           "NIFTY has been moving more than options are pricing."))
    else:
        votes.append(_vote("Option pricing", pricing.title(), None, _W_PRICING,
                           "Priced and real movement are close enough to call fair, or could not "
                           "be compared."))

    # 6. Which side of the day's average price.
    if trend is not None and trend.price_vs_vwap == "ABOVE":
        votes.append(_vote("Versus day's average price", "Above", UPSIDE, _W_VWAP,
                           "Price is above the level the session keeps returning to."))
    elif trend is not None and trend.price_vs_vwap == "BELOW":
        votes.append(_vote("Versus day's average price", "Below", DOWNSIDE, _W_VWAP,
                           "Price is below the level the session keeps returning to."))
    else:
        votes.append(_vote("Versus day's average price", "At it", RANGE, _W_VWAP,
                           "Price is sitting on the day's average, which is neutral by definition."))

    # 7. Trend strength.
    adx = trend.adx if trend is not None else None
    if adx is None:
        votes.append(_vote("Trend strength", "Not available", None, _W_ADX,
                           "Not enough bars to measure trend strength yet."))
    elif adx >= 25:
        target = UPSIDE if trend_label == ms.BULLISH else DOWNSIDE if trend_label == ms.BEARISH else None
        votes.append(_vote("Trend strength", f"Strong (ADX {adx:.0f})", target, _W_ADX,
                           "Directional pressure is real rather than chop."))
    elif adx < 20:
        votes.append(_vote("Trend strength", f"Weak (ADX {adx:.0f})", RANGE, _W_ADX,
                           "Trend strength is below the level that separates a trend from chop."))
    else:
        votes.append(_vote("Trend strength", f"Middling (ADX {adx:.0f})", None, _W_ADX,
                           "Trend strength is in the band that argues for neither."))

    return votes


# ------------------------------------------------------------- the build --


def _nearest(levels: list, above: bool, spot: float) -> float | None:
    """Nearest level above (or below) spot, from the key-level ladder."""
    candidates = [
        l.price for l in levels
        if l.kind in ("RESISTANCE", "SUPPORT") and ((l.price > spot) if above else (l.price < spot))
    ]
    if not candidates:
        return None
    return min(candidates) if above else max(candidates)


def _checklist(
    summary: regime_module.RegimeSummary,
    structure: ms.MarketStructureSummary | None,
    gex_summary: gex_module.GexSummary | None,
    signals: list[setups_module.SetupSignal],
    key_levels: list,
    call_walls: list,
    put_walls: list,
    risk_assessment,
) -> list[ChecklistItem]:
    """Ten conditions, every one read from something already computed.

    The mocked version hardcoded eight ticks and two crosses. These can all
    come out either way, and on a quiet pre-market morning most of them
    correctly come out as crosses.
    """
    armed = [s for s in signals if s.status == setups_module.ARMED]
    actionable = [s for s in armed if s.readiness in (setups_module.NOW, setups_module.WAIT)]
    higher = [tf for tf in (structure.timeframes if structure else []) if tf.enough_data
              and tf.label in ("1D", "1H", "15M")]
    fresh_walls = [w for w in (call_walls + put_walls) if w.freshness == "FRESH"]

    return [
        ChecklistItem(
            "Higher timeframes agree",
            bool(higher) and len({tf.trend for tf in higher}) == 1,
            f"{len(higher)} higher timeframe(s) readable" if higher else "Not enough stored history yet",
        ),
        ChecklistItem(
            "Market structure is clear",
            structure is not None and structure.structure_trend != ms.UNCLEAR,
            structure.structure_trend.title() if structure else "No structure read available",
        ),
        ChecklistItem(
            "Support and resistance identified",
            _nearest(key_levels, True, summary.atm_strike or 0) is not None
            or _nearest(key_levels, False, summary.atm_strike or 0) is not None,
            f"{len([l for l in key_levels if l.kind in ('RESISTANCE', 'SUPPORT')])} levels on the ladder",
        ),
        ChecklistItem(
            "Option chain is live",
            summary.straddle_price is not None,
            "ATM straddle priced" if summary.straddle_price is not None else "No live chain yet",
        ),
        ChecklistItem(
            "Open interest shows fresh conviction",
            bool(fresh_walls),
            f"{len(fresh_walls)} wall(s) built up today" if fresh_walls
            else "Nearby open interest is stale, not built today",
        ),
        ChecklistItem(
            "Dealer positioning is readable",
            gex_summary is not None and gex_summary.regime != gex_module.GAMMA_UNKNOWN,
            gex_summary.regime.replace("_", " ").title() if gex_summary else "No gamma data",
        ),
        ChecklistItem(
            "Movement is priced sensibly",
            summary.premium_pricing != regime_module.PRICING_UNKNOWN,
            f"Priced {summary.implied_daily_move_points:.0f} vs real "
            f"{summary.realized_daily_move_points:.0f} points"
            if summary.implied_daily_move_points and summary.realized_daily_move_points
            else "Could not compare priced against real movement",
        ),
        ChecklistItem(
            "Market is open and settled",
            summary.session_window in ("MIDDAY", "CLOSING"),
            summary.session_window.title().replace("_", " "),
        ),
        ChecklistItem(
            "Risk window allows a new position",
            risk_assessment is not None and not risk_assessment.avoid_new_entries,
            risk_assessment.reasons[0] if (risk_assessment and risk_assessment.reasons)
            else "No restriction on this window",
        ),
        ChecklistItem(
            "An entry trigger exists",
            bool(actionable),
            f"{len(actionable)} setup(s) armed and not already past their level" if actionable
            else "No setup is armed with its level still ahead",
        ),
    ]


def build(
    *,
    spot_price: float,
    summary: regime_module.RegimeSummary,
    structure: ms.MarketStructureSummary | None,
    trend,
    gex_summary: gex_module.GexSummary | None,
    signals: list[setups_module.SetupSignal],
    key_levels: list,
    call_walls: list,
    put_walls: list,
    risk_assessment,
) -> ScenarioSet:
    votes = _collect_votes(summary, structure, trend, gex_summary)
    assigned = sum(ev.weight for target, ev in votes if target is not None) or 1.0

    resistance = _nearest(key_levels, True, spot_price)
    support = _nearest(key_levels, False, spot_price)
    move = summary.implied_daily_move_points or 0.0
    reach = move * _TARGET_FRACTION

    def evidence_for(key: str) -> list[ScenarioEvidence]:
        return [ev for target, ev in votes if target == key]

    def share(key: str) -> float:
        return round(sum(ev.weight for ev in evidence_for(key)) / assigned * 100, 1)

    def setups_for(keys: tuple[str, ...]) -> list[str]:
        return [s.name for s in signals if s.key in keys and s.status == setups_module.ARMED]

    scenarios = [
        Scenario(
            key=UPSIDE,
            name="Breaks higher",
            direction="BULLISH",
            evidence_share=share(UPSIDE),
            trigger_level=resistance,
            trigger=(
                f"a 5-minute candle closes above {resistance:.0f}, the nearest level overhead"
                if resistance is not None
                else "a 5-minute candle closes above the nearest level overhead (none identified yet)"
            ),
            invalidation=(
                f"price closes back below {resistance:.0f}. A failed break is not a weaker version "
                "of this scenario, it is the range scenario."
                if resistance is not None
                else "price fails to hold above whichever level it breaks."
            ),
            target_level=round(resistance + reach, 1) if resistance is not None and reach else None,
            what_it_means="Favours buying calls, and rules out selling them at that level.",
            evidence=evidence_for(UPSIDE),
            matching_setups=setups_for(("IB_BREAKOUT_LONG", "TREND_PULLBACK_LONG", "WALL_FADE_PUT",
                                        "IB_FAILURE_FADE_LONG")),
        ),
        Scenario(
            key=RANGE,
            name="Stays in the range",
            direction="NEUTRAL",
            evidence_share=share(RANGE),
            trigger_level=None,
            trigger=(
                f"price keeps failing at {resistance:.0f} and holding {support:.0f} -- rejection at "
                "the edges, not a break of them."
                if resistance is not None and support is not None
                else "price keeps rejecting from the edges of its range rather than breaking them."
            ),
            invalidation=(
                f"a 5-minute close outside {support:.0f} – {resistance:.0f}."
                if resistance is not None and support is not None
                else "a decisive close beyond either edge of the range."
            ),
            target_level=None,
            what_it_means="Favours selling premium at the edges, and punishes buying either side.",
            evidence=evidence_for(RANGE),
            matching_setups=setups_for(("RANGE_SHORT_STRADDLE", "WALL_FADE_CALL", "WALL_FADE_PUT",
                                        "EXPIRY_PIN_FADE")),
        ),
        Scenario(
            key=DOWNSIDE,
            name="Breaks lower",
            direction="BEARISH",
            evidence_share=share(DOWNSIDE),
            trigger_level=support,
            trigger=(
                f"a 5-minute candle closes below {support:.0f}, the nearest level underneath"
                if support is not None
                else "a 5-minute candle closes below the nearest level underneath (none identified yet)"
            ),
            invalidation=(
                f"price closes back above {support:.0f}. A failed break is the range scenario, not "
                "a weaker version of this one."
                if support is not None
                else "price fails to hold below whichever level it breaks."
            ),
            target_level=round(support - reach, 1) if support is not None and reach else None,
            what_it_means="Favours buying puts, and rules out selling them at that level.",
            evidence=evidence_for(DOWNSIDE),
            matching_setups=setups_for(("IB_BREAKOUT_SHORT", "TREND_PULLBACK_SHORT", "WALL_FADE_CALL",
                                        "IB_FAILURE_FADE_SHORT")),
        ),
    ]
    scenarios.sort(key=lambda s: -s.evidence_share)

    checklist = _checklist(summary, structure, gex_summary, signals, key_levels,
                           call_walls, put_walls, risk_assessment)
    passed = sum(1 for item in checklist if item.passed)
    failed = [item.name for item in checklist if not item.passed]

    if summary.session_window == "CLOSED":
        verdict = STAND_DOWN
        note = "The market is closed. This is a read on the last session, not something to act on."
    elif any(s.status == setups_module.ARMED and s.readiness == setups_module.NOW for s in signals):
        verdict = TRADE
        note = "A setup is armed and price is at its level. See the AI Analyst page for the trade."
    elif any(s.status == setups_module.ARMED for s in signals):
        verdict = WAIT
        note = (
            "A setup is armed but price has not reached its trigger. "
            + (f"Still unmet: {', '.join(failed)}." if failed else "")
        )
    else:
        verdict = STAND_DOWN
        note = (
            "No setup is armed. "
            + (f"Unmet conditions: {', '.join(failed)}." if failed else "")
        )

    return ScenarioSet(
        spot_price=spot_price,
        scenarios=scenarios,
        checklist=checklist,
        checklist_passed=passed,
        checklist_total=len(checklist),
        verdict=verdict,
        verdict_note=note,
        caveat=(
            "The percentage on each scenario is the share of today's measurable evidence pointing "
            "that way -- not a probability, and not fitted to any historical outcome. Read it as "
            "'most of what I can measure points here', never as 'this happens six times in ten'."
        ),
    )

"""The user's own trading rule, reverse-engineered from their Excel workbook
(nifty_options_trading.xlsx) -- exact formulas, not a paraphrase. Pure functions,
no I/O, same style as the other signals/ modules.

ATM selection: among 3 candidate strikes (spot rounded to nearest 50, and +/-50),
ATM is whichever has the smallest |CE_Close - PE_Close| (premium symmetry).

Support/Resistance: from the ATM strike's own CE/PE Close (used as "premium").

Per-leg buyer/seller domination (CE and PE independently): Close within
threshold_points of the day's High -> Buyer; within threshold_points of the day's
Low -> Seller; else Indecision. The sign check is deliberate, not just abs(diff) <=
threshold: replicates the spreadsheet's IF(AND(ABS(diff)<=35, diff<0), ...) exactly,
so e.g. Close == High precisely is Indecision, not Buyer.
"""

from __future__ import annotations

from dataclasses import dataclass

from algooptionx.research.ingestion.option_ohlc import SessionOhlc

BUYER, SELLER, INDECISION = "Buyer", "Seller", "Indecision"
PANIC, PROFIT_BOOKING, SIDEWAYS = "Panic", "Profit Booking", "Sideways"
DEFAULT_THRESHOLD_POINTS = 35.0
DEFAULT_TARGET_POINTS_PER_DAY = 20.0
DEFAULT_MAX_TRADES_PER_DAY = 2
SELL = "SELL"


class HlcAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class StrikeQuote:
    strike: float
    ce: SessionOhlc | None
    pe: SessionOhlc | None


@dataclass(frozen=True)
class LegAnalysis:
    high: float
    close: float
    low: float
    close_high_diff: float
    close_low_diff: float
    domination: str  # Buyer | Seller | Indecision
    market_type: str  # Panic | Profit Booking | Sideways


@dataclass(frozen=True)
class RangeBand:
    """Weekly/monthly support-resistance band: the close rounded down/up to the
    nearest 100 gives two strikes; each strike's combined CE+PE close (not the
    ATM's single straddle like the daily panel) gives that strike's own Sell/Buy
    level. See hlc_worker.py for how close/anchor dates are resolved."""

    close: float
    low_strike: float
    high_strike: float
    low_premium: float  # CE close + PE close, combined, at low_strike
    high_premium: float  # CE close + PE close, combined, at high_strike
    sell_low: float
    sell_high: float
    buy_low: float
    buy_high: float


@dataclass(frozen=True)
class TradeLeg:
    """One planned SELL on the ATM strike's CE or PE, in premium points --
    entry/target are option-premium levels, not underlying levels.

    stop_loss is deliberately a rule description, not a number: the user's rule
    is "exit if premium breaks the high of the *previous completed 5-minute
    candle*", which only exists once that session's intraday candles start
    forming -- there's nothing to compute before market open. entry_trigger and
    target ARE fixed at plan time (previous session's close, and that minus the
    day's points target), so those stay numeric."""

    option_type: str  # CE | PE
    action: str  # SELL -- this strategy only ever sells premium, per the sheet's S/R framing
    strike: float
    entry_trigger: float  # premium level to sell at (that leg's own previous-session close)
    stop_rule: str  # human-readable; the actual level is only known live, see journal_grading.py
    target: float  # premium level to book profit at
    target_points: float  # entry_trigger - target, i.e. the premium points captured


@dataclass(frozen=True)
class TradePlan:
    """What to do, derived from combined_signal. Sits out (empty legs) on
    Strong Bullish/Indecision days -- see build_trade_plan().

    session_date is the completed session this plan's numbers (entry/target)
    were built from; trade_date is the day the plan is actually meant to be
    acted on -- the *next* trading session after session_date, not
    session_date itself. Easy to get backwards: reading Friday's close builds
    a plan for Monday, not "Friday's plan"."""

    session_date: str
    trade_date: str
    legs: list[TradeLeg]
    note: str


@dataclass(frozen=True)
class HlcResult:
    session_date: str  # ISO date -- the last completed trading day this read is from
    nifty_close: float  # NIFTY's own closing price on session_date (spreadsheet's A7 input)
    candidates: list[StrikeQuote]
    atm_strike: float
    atm_ce_close: float
    atm_pe_close: float
    max_resistance: float
    min_resistance: float
    min_support: float
    max_support: float
    ce: LegAnalysis
    pe: LegAnalysis
    combined_signal: str
    weekly: RangeBand | None = None
    monthly: RangeBand | None = None
    trade_plan: TradePlan | None = None


def select_atm(candidates: list[StrikeQuote]) -> StrikeQuote:
    complete = [c for c in candidates if c.ce is not None and c.pe is not None]
    if not complete:
        raise HlcAnalysisError("No candidate strike has both CE and PE session data yet.")
    return min(complete, key=lambda c: abs(c.ce.close - c.pe.close))


def analyze_leg(ohlc: SessionOhlc, threshold_points: float = DEFAULT_THRESHOLD_POINTS) -> LegAnalysis:
    close_high_diff = ohlc.close - ohlc.high
    close_low_diff = ohlc.close - ohlc.low

    if abs(close_high_diff) <= threshold_points and close_high_diff < 0:
        domination = BUYER
    elif abs(close_low_diff) <= threshold_points and close_low_diff > 0:
        domination = SELLER
    else:
        domination = INDECISION

    market_type = {BUYER: PANIC, SELLER: PROFIT_BOOKING, INDECISION: SIDEWAYS}[domination]

    return LegAnalysis(
        high=ohlc.high,
        close=ohlc.close,
        low=ohlc.low,
        close_high_diff=close_high_diff,
        close_low_diff=close_low_diff,
        domination=domination,
        market_type=market_type,
    )


def combined_signal(ce_domination: str, pe_domination: str) -> str:
    if ce_domination == BUYER and pe_domination == BUYER:
        return "Strong Bullish (Panic Buying)"
    if ce_domination == SELLER and pe_domination == SELLER:
        return "Strong Bearish (Profit Booking)"
    if ce_domination == BUYER and pe_domination == SELLER:
        return "Mixed - CE Bullish / PE Bearish"
    if ce_domination == SELLER and pe_domination == BUYER:
        return "Mixed - CE Bearish / PE Bullish"
    return "Indecision - Sideways Market"


def range_strikes(close: float, step: float = 100.0) -> tuple[float, float]:
    """Nearest strikes bracketing close, floored/ceiled to step -- not an
    ATM-symmetry search like the daily panel, just a plain round-down/round-up.
    high is always low + step: when close isn't an exact multiple that IS the
    ceiling; when it is, this still bumps high up by one full step so the two
    bounds are never equal."""
    low = (close // step) * step
    high = low + step
    return low, high


def range_band(
    close: float, low_strike: float, low_premium: float, high_strike: float, high_premium: float
) -> RangeBand:
    return RangeBand(
        close=close,
        low_strike=low_strike,
        high_strike=high_strike,
        low_premium=low_premium,
        high_premium=high_premium,
        sell_low=low_strike + low_premium,
        sell_high=high_strike + high_premium,
        buy_low=low_strike - low_premium,
        buy_high=high_strike - high_premium,
    )


def analyze(
    candidates: list[StrikeQuote],
    session_date: str,
    nifty_close: float,
    threshold_points: float = DEFAULT_THRESHOLD_POINTS,
) -> HlcResult:
    atm = select_atm(candidates)

    atm_ce_close = atm.ce.close
    atm_pe_close = atm.pe.close
    combined_premium = atm_ce_close + atm_pe_close

    ce_leg = analyze_leg(atm.ce, threshold_points)
    pe_leg = analyze_leg(atm.pe, threshold_points)

    return HlcResult(
        session_date=session_date,
        nifty_close=nifty_close,
        candidates=candidates,
        atm_strike=atm.strike,
        atm_ce_close=atm_ce_close,
        atm_pe_close=atm_pe_close,
        max_resistance=atm.strike + combined_premium,
        min_resistance=atm.strike + atm_ce_close,
        min_support=atm.strike - atm_pe_close,
        max_support=atm.strike - combined_premium,
        ce=ce_leg,
        pe=pe_leg,
        combined_signal=combined_signal(ce_leg.domination, pe_leg.domination),
    )


_STOP_RULE = "Exit if this leg's premium closes above the high of the previous completed 5-minute candle."


def _sell_leg(option_type: str, strike: float, entry_trigger: float, target_points: float) -> TradeLeg:
    return TradeLeg(
        option_type=option_type,
        action=SELL,
        strike=strike,
        entry_trigger=entry_trigger,
        stop_rule=_STOP_RULE,
        target=entry_trigger - target_points,
        target_points=target_points,
    )


def build_trade_plan(
    result: HlcResult,
    trade_date: str,
    target_points_per_day: float = DEFAULT_TARGET_POINTS_PER_DAY,
    max_trades_per_day: int = DEFAULT_MAX_TRADES_PER_DAY,
) -> TradePlan:
    """Turns the HLC read into what to actually do today -- extends the
    spreadsheet's only defined action ("Mixed -> sell the weak/Seller-dominated
    leg") to the other 3 combined_signal cases the same way: a Seller-dominated
    leg's premium already deflated into the close, so that's the side this rule
    sells. Strong Bullish (both legs still rising into the close) and Indecision
    (no clear domination on at least one leg) have no Seller-dominated leg to
    sell opposite a clear Buyer-dominated one, so both sit out. See
    hlc_strategy.py module docstring / the plan doc for why this mapping was
    chosen -- it's the one place in this module that's an inference beyond what
    the spreadsheet explicitly specifies, not a direct transcription.

    The four branches below must match combined_signal()'s own four defined
    pairs exactly (SELLER/SELLER, BUYER/BUYER, SELLER/BUYER, BUYER/SELLER) --
    an earlier version used bare `elif ce == SELLER:` here, which also fired
    on ce=SELLER/pe=INDECISION even though combined_signal() itself classifies
    that as "Indecision - Sideways Market", not "Mixed". That meant the plan
    would trade a day the app's own display was calling Indecision -- caught
    live from a real journal entry showing that exact combination."""
    ce, pe = result.ce.domination, result.pe.domination

    if ce == SELLER and pe == SELLER:
        points_each = target_points_per_day / 2
        legs = [
            _sell_leg("CE", result.atm_strike, result.atm_ce_close, points_each),
            _sell_leg("PE", result.atm_strike, result.atm_pe_close, points_each),
        ]
        note = "Strong Bearish (Profit Booking on both legs) -- selling both CE and PE."
    elif ce == BUYER and pe == BUYER:
        legs = []
        note = (
            "Strong Bullish (Panic Buying on both legs) -- both premiums rose into the close, "
            "the opposite of what this rule sells into. Sitting out."
        )
    elif ce == SELLER and pe == BUYER:
        legs = [_sell_leg("CE", result.atm_strike, result.atm_ce_close, target_points_per_day)]
        note = "Mixed -- CE is the Seller-dominated (weak) leg. Selling CE."
    elif pe == SELLER and ce == BUYER:
        legs = [_sell_leg("PE", result.atm_strike, result.atm_pe_close, target_points_per_day)]
        note = "Mixed -- PE is the Seller-dominated (weak) leg. Selling PE."
    else:
        legs = []
        note = "Indecision -- no clear Seller-dominated leg paired with a Buyer-dominated one. Sitting out."

    return TradePlan(
        session_date=result.session_date, trade_date=trade_date, legs=legs[:max_trades_per_day], note=note
    )

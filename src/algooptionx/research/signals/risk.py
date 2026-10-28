"""Position sizing and time-of-day/expiry-day risk awareness.

Grounded in `.claude/skills/nifty-options-domain-knowledge/references/
greeks-iv-timing.md` (loaded before writing this): the trade plan's real
risk isn't theta (a structural tailwind for the seller), it's **gamma**,
concentrated in three windows -- the first 15-30 minutes after open (IV
unstable, direction/gamma unresolved -- many professional intraday sellers
explicitly avoid new entries here), the last 1-2 hours before close (theta
acceleration is a tailwind but gamma risk is elevated too), and especially
the weekly expiry session itself (ATM options carry simultaneously the
highest theta *and* highest gamma on expiry day). None of that is
represented in `hlc_strategy.py`'s fixed rule today. This module doesn't
change that rule -- it adds the risk-sizing layer the requirement doc's
Risk Engine (§31-32) calls for, informed by it.

Deliberately does NOT try to compute one single "correct" stop distance
ahead of time: hlc_strategy.py's stop is a *live* rule (the previous
completed 5-minute candle's high/low), not a fixed pre-market number, so
pretending to know it in advance would be false precision. Position sizing
here is instead a reference table across plausible stop distances, plus one
concrete estimate using the trade plan's own already-known level distance --
both clearly labeled as such.

Also does NOT implement true real-time intraday P&L tracking -- this app
only grades a session's outcome retrospectively, once, at the next session's
rollover (see hlc_worker.py) by design; there is no live position/order feed
to track a running "today's P&L so far" against. The "daily risk" view here
is honestly scoped to the most recently *graded* day, not a live guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from algooptionx.research.ingestion.option_ohlc import MARKET_CLOSE, MARKET_OPEN, SATURDAY

OPENING, MIDDAY, CLOSING, CLOSED = "OPENING", "MIDDAY", "CLOSING", "CLOSED"

# First-cut calibration, documented per this project's usual honesty
# standard -- not a precisely-sourced number, a reasonable reading of the
# domain research's qualitative findings (avoid/reduce in opening and
# closing windows, worst combination is closing-hour-on-expiry-day).
_CLOSED_REASON = "The market is closed. Nothing here can be acted on until the next session opens."

_RISK_TABLE: dict[tuple[str, bool], tuple[float, bool, list[str]]] = {
    (CLOSED, False): (0.0, True, [_CLOSED_REASON]),
    (CLOSED, True): (0.0, True, [_CLOSED_REASON]),
    (OPENING, False): (0.5, True, ["First 30 minutes: IV/gamma unresolved after the open -- many professional intraday sellers avoid new entries here."]),
    (OPENING, True): (0.5, True, ["First 30 minutes on expiry day: opening uncertainty stacked on already-elevated expiry-day gamma."]),
    (MIDDAY, False): (1.0, False, []),
    (MIDDAY, True): (0.75, False, ["Expiry day: ATM options carry both the highest theta and the highest gamma today -- size down even outside the closing window."]),
    (CLOSING, False): (0.75, False, ["Final 1-2 hours: theta acceleration favors the seller, but gamma risk is elevated -- keep size moderate."]),
    (CLOSING, True): (0.25, True, ["Final 1-2 hours on expiry day: the single highest-gamma window per the domain research -- avoid new entries, reduce existing size."]),
}


@dataclass(frozen=True)
class RiskAssessment:
    window: str  # OPENING | MIDDAY | CLOSING
    is_expiry_day: bool
    size_multiplier: float  # applied on top of the normal max-risk-per-trade sizing
    avoid_new_entries: bool
    reasons: list[str]


@dataclass(frozen=True)
class PositionSizeRow:
    stop_distance_points: float
    lots: int
    quantity: int
    risk_amount: float  # actual ₹ at risk for `lots` at this stop distance


@dataclass(frozen=True)
class PositionSizing:
    capital: float
    max_risk_per_trade: float  # ₹, before the time-of-day multiplier
    lot_size: int
    risk_assessment: RiskAssessment
    table: list[PositionSizeRow]
    estimated: PositionSizeRow | None  # using the trade plan's own known level distance, if available


@dataclass(frozen=True)
class DailyRiskStatus:
    as_of_trade_date: str | None  # the most recently *graded* trade date this reflects, None if none graded yet
    realized_points: float | None
    realized_amount: float | None
    max_daily_loss: float
    remaining_budget: float
    locked: bool


def classify_session_window(now: datetime, opening_minutes: int = 30, closing_minutes: int = 90) -> str:
    """Which part of the trading session `now` falls in, or CLOSED.

    CLOSED matters and was missing. Without it, any time before 09:15 was
    classified OPENING and any time after 15:30 CLOSING, so opening the app at
    six in the morning produced "First 30 minutes: volatility is still
    unwinding from the overnight gap" -- stated confidently about a market
    that would not open for another three hours. Weekends had the same
    problem. Anything the engine says about a window has to be true of the
    clock it is actually looking at."""
    if now.weekday() >= SATURDAY:
        return CLOSED

    market_open = datetime.combine(now.date(), MARKET_OPEN)
    market_close = datetime.combine(now.date(), MARKET_CLOSE)

    if now < market_open or now > market_close:
        return CLOSED
    if now <= market_open + timedelta(minutes=opening_minutes):
        return OPENING
    if now >= market_close - timedelta(minutes=closing_minutes):
        return CLOSING
    return MIDDAY


def assess_risk(now: datetime, is_expiry_day: bool, opening_minutes: int = 30, closing_minutes: int = 90) -> RiskAssessment:
    window = classify_session_window(now, opening_minutes, closing_minutes)
    multiplier, avoid, reasons = _RISK_TABLE[(window, is_expiry_day)]
    return RiskAssessment(window=window, is_expiry_day=is_expiry_day, size_multiplier=multiplier, avoid_new_entries=avoid, reasons=reasons)


def _size_row(stop_distance_points: float, capital: float, max_risk_pct_per_trade: float, lot_size: int, size_multiplier: float) -> PositionSizeRow:
    max_risk = capital * max_risk_pct_per_trade
    risk_per_lot = stop_distance_points * lot_size
    if risk_per_lot <= 0:
        return PositionSizeRow(stop_distance_points, 0, 0, 0.0)
    raw_lots = int(max_risk // risk_per_lot)
    lots = int(raw_lots * size_multiplier)
    return PositionSizeRow(stop_distance_points, lots, lots * lot_size, lots * risk_per_lot)


def position_sizing(
    capital: float,
    max_risk_pct_per_trade: float,
    lot_size: int,
    risk_assessment: RiskAssessment,
    stop_distances: tuple[float, ...] = (10, 15, 20, 25, 30, 40, 50),
    estimated_stop_distance: float | None = None,
) -> PositionSizing:
    table = [_size_row(d, capital, max_risk_pct_per_trade, lot_size, risk_assessment.size_multiplier) for d in stop_distances]
    estimated = (
        _size_row(estimated_stop_distance, capital, max_risk_pct_per_trade, lot_size, risk_assessment.size_multiplier)
        if estimated_stop_distance is not None and estimated_stop_distance > 0
        else None
    )
    return PositionSizing(
        capital=capital,
        max_risk_per_trade=capital * max_risk_pct_per_trade,
        lot_size=lot_size,
        risk_assessment=risk_assessment,
        table=table,
        estimated=estimated,
    )


def daily_risk_status(
    last_graded: tuple[str, float] | None,  # (trade_date, realized_points), the most recently graded day
    capital: float,
    lot_size: int,
    max_daily_loss_pct: float,
) -> DailyRiskStatus:
    max_daily_loss = capital * max_daily_loss_pct
    if last_graded is None:
        return DailyRiskStatus(None, None, None, max_daily_loss, max_daily_loss, False)

    trade_date, realized_points = last_graded
    realized_amount = realized_points * lot_size
    loss_amount = max(0.0, -realized_amount)  # only a loss eats into the daily budget
    remaining = max(0.0, max_daily_loss - loss_amount)
    locked = loss_amount >= max_daily_loss
    return DailyRiskStatus(trade_date, realized_points, realized_amount, max_daily_loss, remaining, locked)

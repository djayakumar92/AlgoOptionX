"""Aggregate statistics over a range of graded Journal entries -- the output
side of backtesting. Pure and DB-free so it's directly testable: the
DhanHQ-fetching orchestration (backtest_worker.py) hands this already-graded
rows, in chronological trade_date order.

Deliberately omits Sharpe/Sortino (the requirement doc's §47 list includes
them): both need a defined risk-free rate and a consistent per-period return
series, neither of which this app has a real basis for yet -- computing a
number here would be false precision, not a metric. Average R *is* included
since it has a clean, real definition available: realized_points divided by
the trade's own planned target_points.
"""

from __future__ import annotations

from dataclasses import dataclass

TARGET_HIT, STOP_HIT, OPEN_AT_CLOSE, NOT_TRIGGERED, NO_TRADE = (
    "TARGET_HIT", "STOP_HIT", "OPEN_AT_CLOSE", "NOT_TRIGGERED", "NO_TRADE"
)
_REALIZED_OUTCOMES = {TARGET_HIT, STOP_HIT, OPEN_AT_CLOSE}


@dataclass(frozen=True)
class GradedTrade:
    trade_date: str
    outcome: str
    realized_points: float | None
    target_points: float | None


@dataclass(frozen=True)
class BacktestStats:
    total_days: int
    graded_trades: int  # TARGET_HIT + STOP_HIT + OPEN_AT_CLOSE -- trades with a real realized P&L
    no_trade_days: int
    not_triggered: int
    net_points: float
    win_rate: float | None  # share of graded_trades with realized_points > 0; None if graded_trades == 0
    profit_factor: float | None  # sum(wins) / sum(|losses|); None if no losses to divide by
    expectancy_points: float | None  # mean realized_points per graded trade
    avg_r: float | None  # mean(realized_points / target_points) over trades with a target
    max_drawdown_points: float  # largest peak-to-trough drop in cumulative realized points
    largest_win: float | None
    largest_loss: float | None  # a negative number (or None if no losses)
    max_consecutive_losses: int


def compute_stats(trades: list[GradedTrade], total_days: int) -> BacktestStats:
    """trades: every graded (non-PENDING) Journal row in the backtest's date
    range, in chronological trade_date order -- may include multiple rows
    per day (e.g. a Strong Bearish day sells both legs). total_days: the
    count of trading days actually covered (including NO_TRADE/sat-out
    days), for an honest "graded_trades out of how many days" context."""
    realized = [t for t in trades if t.outcome in _REALIZED_OUTCOMES and t.realized_points is not None]
    no_trade_days = sum(1 for t in trades if t.outcome == NO_TRADE)
    not_triggered = sum(1 for t in trades if t.outcome == NOT_TRIGGERED)

    points = [t.realized_points for t in realized]
    net_points = sum(points) if points else 0.0

    wins = [p for p in points if p > 0]
    losses = [p for p in points if p <= 0]

    win_rate = len(wins) / len(points) if points else None
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else None
    expectancy_points = net_points / len(points) if points else None

    r_values = [t.realized_points / t.target_points for t in realized if t.target_points]
    avg_r = sum(r_values) / len(r_values) if r_values else None

    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for p in points:
        cumulative += p
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)

    max_consecutive_losses = 0
    current_streak = 0
    for p in points:
        if p <= 0:
            current_streak += 1
            max_consecutive_losses = max(max_consecutive_losses, current_streak)
        else:
            current_streak = 0

    return BacktestStats(
        total_days=total_days,
        graded_trades=len(points),
        no_trade_days=no_trade_days,
        not_triggered=not_triggered,
        net_points=round(net_points, 2),
        win_rate=round(win_rate, 4) if win_rate is not None else None,
        profit_factor=round(profit_factor, 3) if profit_factor is not None else None,
        expectancy_points=round(expectancy_points, 3) if expectancy_points is not None else None,
        avg_r=round(avg_r, 3) if avg_r is not None else None,
        max_drawdown_points=round(max_drawdown, 2),
        largest_win=round(max(wins), 2) if wins else None,
        largest_loss=round(min(losses), 2) if losses else None,
        max_consecutive_losses=max_consecutive_losses,
    )

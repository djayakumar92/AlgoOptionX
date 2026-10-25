from dhan_analyzer.signals.backtest_stats import GradedTrade, compute_stats

TARGET_HIT, STOP_HIT, OPEN_AT_CLOSE, NOT_TRIGGERED, NO_TRADE = (
    "TARGET_HIT", "STOP_HIT", "OPEN_AT_CLOSE", "NOT_TRIGGERED", "NO_TRADE"
)


def _trades():
    return [
        GradedTrade("2026-09-01", TARGET_HIT, 8.0, 10.0),
        GradedTrade("2026-09-02", STOP_HIT, -5.0, 5.0),
        GradedTrade("2026-09-03", STOP_HIT, -3.0, 3.0),
        GradedTrade("2026-09-04", TARGET_HIT, 10.0, 10.0),
        GradedTrade("2026-09-05", STOP_HIT, -2.0, 2.0),
    ]


def test_compute_stats_known_sequence():
    trades = _trades() + [
        GradedTrade("2026-09-06", NO_TRADE, None, None),
        GradedTrade("2026-09-07", NOT_TRIGGERED, None, None),
    ]
    stats = compute_stats(trades, total_days=7)

    assert stats.total_days == 7
    assert stats.graded_trades == 5
    assert stats.no_trade_days == 1
    assert stats.not_triggered == 1
    assert stats.net_points == 8.0
    assert stats.win_rate == 0.4
    assert stats.profit_factor == 1.8
    assert stats.expectancy_points == 1.6
    assert stats.avg_r == -0.24
    assert stats.max_drawdown_points == 8.0
    assert stats.largest_win == 10.0
    assert stats.largest_loss == -5.0
    assert stats.max_consecutive_losses == 2


def test_compute_stats_open_at_close_counts_as_realized():
    trades = [GradedTrade("2026-09-01", OPEN_AT_CLOSE, 3.5, 10.0)]
    stats = compute_stats(trades, total_days=1)
    assert stats.graded_trades == 1
    assert stats.net_points == 3.5
    assert stats.win_rate == 1.0


def test_compute_stats_no_graded_trades_returns_none_ratios_not_crash():
    trades = [
        GradedTrade("2026-09-01", NO_TRADE, None, None),
        GradedTrade("2026-09-02", NOT_TRIGGERED, None, None),
    ]
    stats = compute_stats(trades, total_days=2)
    assert stats.graded_trades == 0
    assert stats.net_points == 0.0
    assert stats.win_rate is None
    assert stats.profit_factor is None
    assert stats.expectancy_points is None
    assert stats.avg_r is None
    assert stats.largest_win is None
    assert stats.largest_loss is None
    assert stats.max_consecutive_losses == 0


def test_compute_stats_all_wins_profit_factor_is_none_no_losses_to_divide_by():
    trades = [GradedTrade("2026-09-01", TARGET_HIT, 5.0, 5.0)]
    stats = compute_stats(trades, total_days=1)
    assert stats.profit_factor is None
    assert stats.win_rate == 1.0


def test_compute_stats_empty_input():
    stats = compute_stats([], total_days=0)
    assert stats.graded_trades == 0
    assert stats.net_points == 0.0
    assert stats.max_drawdown_points == 0.0
    assert stats.max_consecutive_losses == 0

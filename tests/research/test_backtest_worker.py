from datetime import date

from algooptionx.research.api.backtest_worker import trading_days


def test_trading_days_excludes_weekends():
    # 2026-08-24 is a Monday, 2026-08-30 is a Sunday.
    days = trading_days(date(2026, 8, 24), date(2026, 8, 30))
    assert days == [date(2026, 8, 24), date(2026, 8, 25), date(2026, 8, 26), date(2026, 8, 27), date(2026, 8, 28)]


def test_trading_days_single_weekday():
    assert trading_days(date(2026, 8, 25), date(2026, 8, 25)) == [date(2026, 8, 25)]


def test_trading_days_single_weekend_day_is_empty():
    assert trading_days(date(2026, 8, 29), date(2026, 8, 29)) == []


def test_trading_days_start_after_end_is_empty():
    assert trading_days(date(2026, 8, 25), date(2026, 8, 20)) == []

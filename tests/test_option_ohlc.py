from datetime import datetime

from dhan_analyzer.ingestion.option_ohlc import last_completed_trading_day

# 2026-08-19 is a Wednesday; 2026-08-22 is a Saturday; 2026-08-24 is a Monday.


def test_before_market_close_uses_previous_day():
    as_of = datetime(2026, 8, 19, 10, 0)  # Wednesday, market open
    assert last_completed_trading_day(as_of) == datetime(2026, 8, 18).date()


def test_after_market_close_uses_same_day():
    as_of = datetime(2026, 8, 19, 16, 0)  # Wednesday, after 15:30 close
    assert last_completed_trading_day(as_of) == datetime(2026, 8, 19).date()


def test_weekend_falls_back_to_friday():
    as_of = datetime(2026, 8, 22, 12, 0)  # Saturday
    assert last_completed_trading_day(as_of) == datetime(2026, 8, 21).date()  # Friday


def test_monday_before_open_falls_back_to_friday():
    as_of = datetime(2026, 8, 24, 8, 0)  # Monday, before market open
    assert last_completed_trading_day(as_of) == datetime(2026, 8, 21).date()  # Friday


def test_back_parameter_steps_further_for_holiday_retry():
    as_of = datetime(2026, 8, 19, 16, 0)  # Wednesday, after close
    assert last_completed_trading_day(as_of, back=1) == datetime(2026, 8, 18).date()

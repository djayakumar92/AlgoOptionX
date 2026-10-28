"""Pure calendar-math tests for the HLC worker's weekly/monthly anchor-date
resolution -- no network access, no DhanHQ client needed."""

from datetime import date

from algooptionx.research.api.hlc_worker import (
    _monthly_anchor_date,
    _monthly_expiry,
    _weekly_anchor_date,
)


def test_weekly_anchor_date_from_tracked_expiry():
    # tracked_expiry is the upcoming Tuesday weekly expiry; anchor is the
    # Wednesday right after the *previous* week's Tuesday expiry.
    assert _weekly_anchor_date(date(2026, 8, 25)) == date(2026, 8, 19)


def test_monthly_expiry_is_last_tuesday_of_month():
    # August 2026: Tuesdays are 4, 11, 18, 25 -> last is 25.
    assert _monthly_expiry(date(2026, 8, 10)) == date(2026, 8, 25)


def test_monthly_anchor_date_is_wednesday_after_previous_months_last_tuesday():
    # July 2026: Tuesdays are 7, 14, 21, 28 -> last is 28 -> anchor Wed 29 Jul.
    assert _monthly_anchor_date(date(2026, 8, 10)) == date(2026, 7, 29)


def test_monthly_anchor_date_handles_december_to_january_rollover():
    # December 2026: Tuesdays are 1, 8, 15, 22, 29 -> last is 29 -> anchor Wed 30 Dec.
    assert _monthly_anchor_date(date(2027, 1, 5)) == date(2026, 12, 30)


def test_monthly_expiry_handles_january_itself():
    # January 2027: Tuesdays are 5, 12, 19, 26 -> last is 26.
    assert _monthly_expiry(date(2027, 1, 15)) == date(2027, 1, 26)

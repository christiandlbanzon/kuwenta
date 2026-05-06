from datetime import date, datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from app.tools._periods import resolve_period
from app.tools.finance_tools import Period

MANILA = ZoneInfo("Asia/Manila")


@freeze_time("2026-05-15 04:00:00")  # 12:00 noon in Asia/Manila (UTC+8)
def test_this_month() -> None:
    start, end = resolve_period(Period(kind="this_month"))
    assert start.date() == date(2026, 5, 1)
    assert start.tzinfo is not None
    assert end.date() == date(2026, 5, 15)


@freeze_time("2026-05-15 04:00:00")  # 12:00 noon in Asia/Manila (UTC+8)
def test_last_month() -> None:
    start, end = resolve_period(Period(kind="last_month"))
    assert start.date() == date(2026, 4, 1)
    assert end.date() == date(2026, 4, 30)


@freeze_time("2026-01-15 04:00:00")  # 12:00 noon in Asia/Manila (UTC+8)
def test_last_month_crosses_year_boundary() -> None:
    start, end = resolve_period(Period(kind="last_month"))
    assert start.date() == date(2025, 12, 1)
    assert end.date() == date(2025, 12, 31)


@freeze_time("2026-05-15 04:00:00")  # 12:00 noon in Asia/Manila (UTC+8)
def test_last_7_days_inclusive() -> None:
    start, end = resolve_period(Period(kind="last_7_days"))
    # 7 days inclusive of today => May 9 .. May 15
    assert start.date() == date(2026, 5, 9)
    assert end.date() == date(2026, 5, 15)


@freeze_time("2026-05-15 04:00:00")  # 12:00 noon in Asia/Manila (UTC+8)
def test_this_year() -> None:
    start, end = resolve_period(Period(kind="this_year"))
    assert start.date() == date(2026, 1, 1)
    assert end.date() == date(2026, 5, 15)


def test_custom_period_requires_start_and_end() -> None:
    import pytest

    with pytest.raises(ValueError):
        resolve_period(Period(kind="custom"))


def test_custom_period_uses_inclusive_end_of_day() -> None:
    p = Period(kind="custom", start=date(2026, 4, 1), end=date(2026, 4, 30))
    start, end = resolve_period(p)
    assert start.hour == 0 and start.minute == 0
    # end-of-day is 23:59:59.999999
    assert end.hour == 23 and end.minute == 59

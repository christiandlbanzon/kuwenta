"""Period resolution.

Converts a `Period` (kind=this_month/last_month/this_year/last_7_days/last_30_days/custom)
into concrete (start, end) datetimes in the user's timezone. Both ends are INCLUSIVE
(per the contract documented in the qa_planner prompt).
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.tools.finance_tools import Period


def _now(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)


def _start_of_day(d: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, time.min, tzinfo=tz)


def _end_of_day(d: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, time.max, tzinfo=tz)


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _last_of_month(d: date) -> date:
    if d.month == 12:
        first_next = date(d.year + 1, 1, 1)
    else:
        first_next = date(d.year, d.month + 1, 1)
    return first_next - timedelta(days=1)


def resolve_period(period: Period, *, timezone: str = "Asia/Manila") -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone)
    now = _now(tz)
    today = now.date()

    if period.kind == "this_month":
        return _start_of_day(_first_of_month(today), tz), now
    if period.kind == "last_month":
        first_this = _first_of_month(today)
        last_prev = first_this - timedelta(days=1)
        first_prev = _first_of_month(last_prev)
        return _start_of_day(first_prev, tz), _end_of_day(last_prev, tz)
    if period.kind == "this_year":
        return _start_of_day(date(today.year, 1, 1), tz), now
    if period.kind == "last_7_days":
        return _start_of_day(today - timedelta(days=6), tz), now
    if period.kind == "last_30_days":
        return _start_of_day(today - timedelta(days=29), tz), now
    if period.kind == "custom":
        if period.start is None or period.end is None:
            raise ValueError("custom period requires both start and end")
        return _start_of_day(period.start, tz), _end_of_day(period.end, tz)
    raise ValueError(f"Unknown period kind: {period.kind}")

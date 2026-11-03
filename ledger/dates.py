"""Date helpers shared by the UI and storage layers."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

ISO_FORMAT = "%Y-%m-%d"
MIN_YEAR = 2000
MAX_YEAR = 2099


def today():
    return date.today()


def iso(d):
    return d.strftime(ISO_FORMAT)


def parse_iso(value):
    if not value:
        return None
    try:
        parsed = datetime.strptime(str(value).strip(), ISO_FORMAT).date()
    except (TypeError, ValueError):
        return None
    if not (MIN_YEAR <= parsed.year <= MAX_YEAR):
        return None
    return parsed


def is_valid_iso(value):
    return parse_iso(value) is not None


def month_bounds(year, month):
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return iso(first), iso(last)


def year_bounds(year):
    return "%d-01-01" % year, "%d-12-31" % year


def add_months(d, delta):
    total = d.year * 12 + (d.month - 1) + delta
    year, month_index = divmod(total, 12)
    month = month_index + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def shift_days(d, delta):
    return d + timedelta(days=delta)


def date_range(start, end):
    current = start
    while current <= end:
        yield current
        current = current + timedelta(days=1)


def weekday_cn(d):
    return "一二三四五六日"[d.weekday()]


def human_date(d):
    return "%d月%d日 周%s" % (d.month, d.day, weekday_cn(d))


def month_title(year, month):
    return "%d年%d月" % (year, month)


def short_date(d):
    return "%d/%d" % (d.month, d.day)

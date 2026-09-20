"""Deterministic Japanese bank-business-day calendar for Cloud operations."""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (occurrence - 1))


def _vernal_equinox(year: int) -> int:
    return int(20.8431 + 0.242194 * (year - 1980) - int((year - 1980) / 4))


def _autumnal_equinox(year: int) -> int:
    return int(23.2488 + 0.242194 * (year - 1980) - int((year - 1980) / 4))


def japanese_public_holidays(year: int) -> set[date]:
    """Return statutory holidays, including substitute and citizens' holidays."""
    holidays = {
        date(year, 1, 1),
        _nth_weekday(year, 1, calendar.MONDAY, 2),
        date(year, 2, 11),
        date(year, 2, 23),
        date(year, 3, _vernal_equinox(year)),
        date(year, 4, 29),
        date(year, 5, 3),
        date(year, 5, 4),
        date(year, 5, 5),
        _nth_weekday(year, 7, calendar.MONDAY, 3),
        date(year, 8, 11),
        _nth_weekday(year, 9, calendar.MONDAY, 3),
        date(year, 9, _autumnal_equinox(year)),
        _nth_weekday(year, 10, calendar.MONDAY, 2),
        date(year, 11, 3),
        date(year, 11, 23),
    }
    # A weekday sandwiched between two national holidays is also a holiday.
    changed = True
    while changed:
        changed = False
        cursor = date(year, 1, 2)
        end = date(year, 12, 30)
        while cursor <= end:
            if (
                cursor.weekday() < 5
                and cursor not in holidays
                and cursor - timedelta(days=1) in holidays
                and cursor + timedelta(days=1) in holidays
            ):
                holidays.add(cursor)
                changed = True
            cursor += timedelta(days=1)
    # A Sunday holiday is observed on the next day that is not already a holiday.
    for holiday in sorted(tuple(holidays)):
        if holiday.weekday() != calendar.SUNDAY:
            continue
        substitute = holiday + timedelta(days=1)
        while substitute in holidays:
            substitute += timedelta(days=1)
        holidays.add(substitute)
    return holidays


def is_bank_business_day(value: date) -> bool:
    if value.weekday() >= 5:
        return False
    if (value.month, value.day) in {(12, 31), (1, 1), (1, 2), (1, 3)}:
        return False
    return value not in japanese_public_holidays(value.year)


def add_bank_business_days(value: date, count: int) -> date:
    if count < 0:
        raise ValueError("count must be non-negative")
    cursor = value
    added = 0
    while added < count:
        cursor += timedelta(days=1)
        if is_bank_business_day(cursor):
            added += 1
    return cursor


def fifth_session_from_entry(entry_date: date) -> date:
    """Entry session is day 1; return the fifth official bank-business session."""
    if not is_bank_business_day(entry_date):
        raise ValueError(f"entry date is not a bank business day: {entry_date}")
    return add_bank_business_days(entry_date, 4)

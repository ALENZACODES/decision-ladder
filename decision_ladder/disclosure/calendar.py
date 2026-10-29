"""Day counting for disclosure deadlines.

Two statutory conventions matter and they disagree on "at least N days before":

* federal Interpretation Act s. 27(1): for "clear days" or "at least" N days between two events, BOTH event days
  are excluded, so a statement given on day D satisfies "at least 21 days before" a date R only if R - D >= 22.
* Ontario Legislation Act, 2006 s. 89(3) (as reported by secondary sources): the last day is counted even where the
  reference is to "at least" N days, so R - D >= 21 suffices.

Business days: Saturday and every Ontario holiday under Legislation Act s. 88 are excluded. Treating "business day"
in O. Reg. 191/08 and 188/08 as "not a Saturday or a holiday" is an assumption (the regulations' definition was not
read). Civic Holiday is not on the s. 88 list.
"""
from __future__ import annotations

from datetime import date, timedelta


def _d(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def add_years(d, years: int) -> date:
    d = _d(d)
    try:
        return d.replace(year=d.year + years)
    except ValueError:          # 29 February -> 28 February
        return d.replace(year=d.year + years, day=28)


def easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l) // 433
    month = (h + l - 7 * m + 90) // 25
    return date(year, month, (h + l - 7 * m + 33 * month + 19) % 32)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def ontario_holidays(year: int) -> dict[date, str]:
    """Weekday-relevant holidays under Legislation Act, 2006 s. 88 (Sundays are always holidays and not listed)."""
    es = easter(year)
    may24 = date(year, 5, 24)
    h = {
        date(year, 1, 1): "New Year's Day",
        _nth_weekday(year, 2, 0, 3): "Family Day",
        es - timedelta(days=2): "Good Friday",
        es + timedelta(days=1): "Easter Monday",
        may24 - timedelta(days=may24.weekday()): "Victoria Day",          # Monday on or before May 24
        date(year, 7, 1): "Canada Day",
        _nth_weekday(year, 9, 0, 1): "Labour Day",
        _nth_weekday(year, 10, 0, 2): "Thanksgiving Day",
        date(year, 11, 11): "Remembrance Day",
        date(year, 12, 25): "Christmas Day",
        date(year, 12, 26): "Boxing Day",
    }
    # weekend substitutions as described for s. 88: New Year's and Canada Day on a Sunday move to Monday;
    # Christmas on a Saturday is observed Monday; Christmas on a Sunday adds Tuesday the 27th.
    for md, name in (((1, 1), "New Year's Day (observed)"), ((7, 1), "Canada Day (observed)")):
        d = date(year, *md)
        if d.weekday() == 6:
            h[d + timedelta(days=1)] = name
    xmas = date(year, 12, 25)
    if xmas.weekday() in (5, 6):
        h[date(year, 12, 27)] = "Christmas Day (observed)"
    return h


def is_business_day(d, jurisdiction: str = "ON", extra_holidays: list | None = None) -> bool:
    d = _d(d)
    if d.weekday() >= 5:
        return False
    if extra_holidays and d in {_d(x) for x in extra_holidays}:
        return False
    return not (jurisdiction.upper() == "ON" and d in ontario_holidays(d.year))


def business_days_between(start, end, jurisdiction: str = "ON", extra_holidays: list | None = None) -> int:
    """Business days in (start, end]: first day excluded, last day counted (Legislation Act s. 89(3) convention)."""
    s, e = _d(start), _d(end)
    if e <= s:
        return 0
    return sum(1 for k in range(1, (e - s).days + 1)
               if is_business_day(s + timedelta(days=k), jurisdiction, extra_holidays))


def latest_date_with_business_days_before(event, n: int, jurisdiction: str = "ON",
                                          extra_holidays: list | None = None) -> date:
    """Latest day D such that business_days_between(D, event) >= n."""
    e = _d(event)
    d = e - timedelta(days=1)
    while business_days_between(d, e, jurisdiction, extra_holidays) < n:
        d -= timedelta(days=1)
    return d


def at_least_days_before(earlier, later, n: int, convention: str) -> dict:
    """Is ``earlier`` at least ``n`` days before ``later`` under the named counting convention?

    convention "federal": Interpretation Act s. 27(1), both event days excluded.
    convention "ontario": Legislation Act s. 89(3), first day excluded and last day counted.
    """
    a, b = _d(earlier), _d(later)
    gap = (b - a).days
    if convention == "federal":
        counted, need = gap - 1, n + 1
    elif convention == "ontario":
        counted, need = gap, n
    else:
        raise ValueError("convention must be 'federal' or 'ontario'")
    return {"ok": counted >= n, "days_counted": max(counted, 0), "required": n,
            "latest_compliant_date": (b - timedelta(days=need)).isoformat(),
            "short_by_days": max(0, n - counted)}

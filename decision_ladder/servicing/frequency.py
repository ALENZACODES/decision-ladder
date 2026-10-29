"""Canadian payment frequencies: how many payments a year, how large each one is, and on which dates.

Rates are converted to an equivalent periodic rate for the payment frequency:

* fixed rate, semi-annual compounding (Interest Act s.6): ``i = (1 + r/2) ** (2/n) - 1``
* variable rate, monthly compounding: ``i = (1 + r/12) ** (12/n) - 1``

where ``n`` is payments per year. For monthly payments both reduce to ``engines.payments.monthly_rate``.

Regular frequencies (semi-monthly, bi-weekly, weekly) use the annuity payment that retires the loan over
the amortization at that frequency. *Accelerated* frequencies pay the monthly payment / 2 every two weeks
(26 times a year) or the monthly payment / 4 every week (52 times), so 13 monthly payments' worth is paid
each year instead of 12; that extra month is what shortens the amortization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..engines.payments import monthly_rate, payment as monthly_payment
from ..penalty.daycount import add_months


@dataclass(frozen=True)
class Frequency:
    key: str
    label: str
    per_year: int
    accelerated_divisor: int | None = None   # accelerated: monthly payment / divisor
    step_days: int | None = None             # fixed day step (bi-weekly, weekly); None = calendar based


FREQUENCIES: dict[str, Frequency] = {f.key: f for f in [
    Frequency("monthly", "Monthly", 12),
    Frequency("semi_monthly", "Semi-monthly", 24),
    Frequency("biweekly", "Bi-weekly", 26, step_days=14),
    Frequency("accelerated_biweekly", "Accelerated bi-weekly", 26, 2, 14),
    Frequency("weekly", "Weekly", 52, step_days=7),
    Frequency("accelerated_weekly", "Accelerated weekly", 52, 4, 7),
]}


def get(key: str) -> Frequency:
    """Look up a frequency; accepts 'bi-weekly', 'Accelerated Bi-Weekly', 'semimonthly' and similar spellings."""
    k = str(key).strip().lower().replace("-", "").replace(" ", "_").replace("bi_weekly", "biweekly")
    k = {"semimonthly": "semi_monthly", "accelerated_bi_weekly": "accelerated_biweekly"}.get(k, k)
    if k not in FREQUENCIES:
        raise ValueError(f"unknown frequency {key!r}; use one of {sorted(FREQUENCIES)}")
    return FREQUENCIES[k]


def compounding_for(rate_type: str) -> str:
    if rate_type not in ("fixed", "variable"):
        raise ValueError("rate_type must be 'fixed' or 'variable'")
    return "semi" if rate_type == "fixed" else "monthly"


def periodic_rate(annual_rate_pct: float, per_year: int, compounding: str) -> float:
    """Effective rate per payment period for a quoted annual rate (percent)."""
    if per_year == 12:
        return monthly_rate(annual_rate_pct, compounding)
    if annual_rate_pct < 0:
        raise ValueError("rate must be >= 0")
    r = annual_rate_pct / 100.0
    if compounding == "semi":
        return (1 + r / 2) ** (2 / per_year) - 1
    if compounding == "monthly":
        return (1 + r / 12) ** (12 / per_year) - 1
    raise ValueError("compounding must be 'semi' or 'monthly'")


def annual_from_periodic(i: float, per_year: int, compounding: str) -> float:
    """Inverse of :func:`periodic_rate`: the quoted annual rate (percent) whose periodic rate is ``i``."""
    growth = (1 + i) ** per_year
    if compounding == "semi":
        return 200 * (growth ** 0.5 - 1)
    if compounding == "monthly":
        return 1200 * (growth ** (1 / 12) - 1)
    raise ValueError("compounding must be 'semi' or 'monthly'")


def annuity(principal: float, i: float, n: int) -> float:
    """Level payment retiring ``principal`` in ``n`` periods at periodic rate ``i``."""
    if n <= 0:
        raise ValueError("number of periods must be positive")
    if i == 0:
        return principal / n
    return principal * i / (1 - (1 + i) ** -n)


def regular_payment(principal: float, annual_rate_pct: float, amort_years: float, frequency: str,
                    compounding: str) -> float:
    """Scheduled payment for any Canadian frequency (accelerated = monthly / 2 or / 4)."""
    f = get(frequency)
    if principal <= 0 or amort_years <= 0:
        raise ValueError("principal and amortization must be positive")
    if f.accelerated_divisor:
        return monthly_payment(principal, annual_rate_pct, amort_years, compounding) / f.accelerated_divisor
    if f.per_year == 12:
        return monthly_payment(principal, annual_rate_pct, amort_years, compounding)
    n = max(1, round(amort_years * f.per_year))
    return annuity(principal, periodic_rate(annual_rate_pct, f.per_year, compounding), n)


def payment_date(first: date, frequency: str, k: int) -> date:
    """Date of payment ``k`` (0 = first payment; -1 = the start of the first period).

    Monthly payments keep the first payment's day of month (clamped to month end). Semi-monthly payments
    fall on that day and at the midpoint to the next monthly date (e.g. the 1st and 16th). Bi-weekly and
    weekly payments step exactly 14 or 7 days.
    """
    f = get(frequency)
    if f.step_days:
        return first + timedelta(days=f.step_days * k)
    if f.per_year == 12:
        return add_months(first, k)
    base = add_months(first, k // 2)
    if k % 2 == 0:
        return base
    nxt = add_months(first, k // 2 + 1)
    return base + timedelta(days=(nxt - base).days // 2)


def first_payment_after(funding: date, frequency: str) -> date:
    """First payment one full period after funding (the usual Canadian arrangement)."""
    f = get(frequency)
    if f.step_days:
        return funding + timedelta(days=f.step_days)
    if f.per_year == 12:
        return add_months(funding, 1)
    nxt = add_months(funding, 1)
    return funding + timedelta(days=(nxt - funding).days // 2)


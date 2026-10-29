"""Shared maths for the commercial desk: debt constants, loan back-solving and IRR.

Fixed-rate Canadian mortgages compound semi-annually (Interest Act s.6), so the debt constant reuses
:mod:`decision_ladder.engines.payments`. Private and construction loans are usually quoted with monthly
compounding; every function here takes ``compounding`` so the caller states which convention applies.
"""
from __future__ import annotations

from ..engines import payments


def r2(x: float) -> float:
    return round(float(x), 2)


def pct(x: float, nd: int = 2) -> float:
    return round(float(x) * 100, nd)


def monthly_payment(loan: float, rate_pct: float, amort_years: float, interest_only: bool = False,
                    compounding: str = "semi") -> float:
    """Monthly payment on ``loan``: interest only, or blended principal and interest over ``amort_years``."""
    if loan <= 0:
        return 0.0
    if interest_only:
        return loan * payments.monthly_rate(rate_pct, compounding)
    return payments.payment(loan, rate_pct, amort_years, compounding)


def debt_constant(rate_pct: float, amort_years: float, interest_only: bool = False, compounding: str = "semi") -> float:
    """Annual debt service per dollar of loan."""
    return monthly_payment(1.0, rate_pct, amort_years, interest_only, compounding) * 12


def loan_for_debt_service(annual_debt_service: float, rate_pct: float, amort_years: float,
                          interest_only: bool = False, compounding: str = "semi") -> float:
    """Largest loan whose annual debt service equals ``annual_debt_service`` (the inverse of the constant)."""
    k = debt_constant(rate_pct, amort_years, interest_only, compounding)
    if k <= 0:
        raise ValueError("debt constant must be positive; an interest-only loan needs a rate above zero")
    return max(0.0, annual_debt_service) / k


def npv(rate: float, flows: list[float]) -> float:
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(flows))


def irr(flows: list[float], lo: float = -0.99, hi: float = 1.0, tol: float = 1e-12) -> float:
    """Per-period IRR by bisection. Needs one sign change between ``lo`` and ``hi``."""
    if not (any(f > 0 for f in flows) and any(f < 0 for f in flows)):
        raise ValueError("cash flows need both an advance and repayments")
    f_lo, f_hi = npv(lo, flows), npv(hi, flows)
    if f_lo * f_hi > 0:
        raise ValueError("IRR not bracketed: check the cash flows")
    for _ in range(300):
        mid = (lo + hi) / 2
        f_mid = npv(mid, flows)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def positive(name: str, x: float, allow_zero: bool = False) -> float:
    x = float(x)
    if x < 0 or (x == 0 and not allow_zero):
        raise ValueError(f"{name} must be {'zero or more' if allow_zero else 'positive'}")
    return x


def ratio(name: str, x: float, hi: float = 100.0) -> float:
    """A percentage input between 0 and ``hi``."""
    x = float(x)
    if not 0 <= x <= hi:
        raise ValueError(f"{name} must be between 0 and {hi:g} percent")
    return x

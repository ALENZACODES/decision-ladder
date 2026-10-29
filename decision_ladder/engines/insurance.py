"""Mortgage default insurance premium (CMHC-style schedule) for high-ratio purchases.

Premium rates are the standard published purchase schedule used by CMHC, Sagen and Canada Guaranty
(percent of the loan amount, by loan-to-value). Since Dec 15, 2024 a 30-year insured amortization is
available to first-time buyers and buyers of new builds; a 0.20 percentage-point surcharge applies to
amortizations over 25 years. Provincial sales tax on the premium (ON 8%, QC 9%, SK 6%) is payable in cash
at closing and is NOT added to the loan.

Indicative only: insurers publish their own schedules and can change them. Confirm with the insurer.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from . import insured

PREMIUM_SCHEDULE = (  # (max LTV inclusive, premium % of loan)
    (65.0, 0.60),
    (75.0, 1.70),
    (80.0, 2.40),
    (85.0, 2.80),
    (90.0, 3.10),
    (95.0, 4.00),
)
LONG_AMORT_SURCHARGE = 0.20
PST_ON_PREMIUM = {"ON": 0.08, "QC": 0.09, "SK": 0.06}


@dataclass
class Premium:
    insured: bool
    ltv: float
    premium_rate_pct: float
    premium: float
    pst_on_premium: float
    total_loan: float
    note: str

    def to_dict(self) -> dict:
        return asdict(self)


def premium_rate(ltv: float, amort_years: int) -> float:
    if ltv <= 0:
        raise ValueError("ltv must be positive")
    if ltv > 95.0:
        raise ValueError("insured loans cannot exceed 95% LTV")
    for cap, rate in PREMIUM_SCHEDULE:
        if ltv <= cap + 1e-9:
            return round(rate + (LONG_AMORT_SURCHARGE if amort_years > 25 else 0.0), 2)
    raise AssertionError("unreachable")


def premium(*, price: float, down_payment: float, amort_years: int = 25, province: str = "ON") -> Premium:
    """Premium for a purchase. Uninsured files (>= 20% down or price at/over the cap) return zero."""
    if price <= 0 or down_payment < 0 or down_payment >= price:
        raise ValueError("price must be positive and down payment between 0 and price")
    loan = price - down_payment
    ltv = loan / price * 100
    if not insured.is_insurable(price, down_payment):
        why = ("20% or more down: conventional (uninsured) mortgage" if ltv <= 80
               else "price at or above the insured cap requires 20% down")
        return Premium(False, round(ltv, 2), 0.0, 0.0, 0.0, round(loan, 2), why)
    rate = premium_rate(ltv, amort_years)
    prem = loan * rate / 100
    pst = prem * PST_ON_PREMIUM.get(province.upper(), 0.0)
    note = f"premium {rate:.2f}% of the loan is added to the mortgage"
    if pst:
        note += f"; {province.upper()} PST on the premium is paid in cash at closing"
    return Premium(True, round(ltv, 2), rate, round(prem, 2), round(pst, 2), round(loan + prem, 2), note)

"""HELOCs and readvanceable (combined loan plan) mortgages.

Limits applied (federally regulated lenders, OSFI Guideline B-20 and OSFI's 2022 clarification on
combined loan plans):

* the revolving (non-amortizing) HELOC portion is capped at 65% of property value;
* the whole plan (amortizing mortgage segments + revolving segment) is capped at 80% of value, the legal
  maximum for uninsured lending;
* credit between 65% and 80% must amortize and must not be readvanced: principal repaid on it reduces the
  overall authorized limit until total borrowing is back at 65%.

So the revolving limit is ``min(65% x value, 80% x value - amortizing balances)``; as the amortizing
mortgage is paid down, that room "readvances" into the HELOC up to the 65% ceiling. The lender's
authorized limit, if lower, governs. Provincially regulated lenders (credit unions) may differ.

The minimum HELOC payment is interest only, computed either as rate/12 on the balance (``'monthly'``) or as
balance x rate x days-in-month / 365 (``'actual_365'``), which is how most Canadian lenders bill.
"""
from __future__ import annotations

import calendar
from datetime import date

from .schedule import LoanSpec, build

OSFI_SOURCE = {
    "url": "https://www.osfi-bsif.gc.ca/en/node/467",
    "title": "OSFI: Clarification on the Treatment of Innovative Real Estate Secured Lending Products under Guideline B-20",
    "checked": "2026-10-29",
    "quoted": ["maximum LTV ratio less than or equal to 65 percent for HELOCs is foundational",
               "any CLP overall limit cannot exceed 80 percent LTV"],
    "summarised": ["lending above 65% LTV (up to 80%) must amortize and not be readvanced",
                   "principal paid on the part above 65% reduces the overall authorized limit until it reaches 65%",
                   "the legal maximum LTV for uninsured mortgages is currently 80 percent"],
}
REVOLVING_MAX_LTV = 65.0
COMBINED_MAX_LTV = 80.0


def interest_only_payment(balance: float, rate: float, basis: str = "actual_365", on: date | None = None) -> float:
    """Minimum (interest-only) HELOC payment for one month."""
    if balance < 0 or rate < 0:
        raise ValueError("balance and rate cannot be negative")
    if basis == "monthly":
        return balance * rate / 100 / 12
    if basis == "actual_365":
        on = on or date.today()
        return balance * rate / 100 * calendar.monthrange(on.year, on.month)[1] / 365
    raise ValueError("basis must be 'monthly' or 'actual_365'")


def limits(property_value: float, amortizing_balance: float, authorized_limit: float | None = None,
           combined_ltv: float = COMBINED_MAX_LTV, revolving_ltv: float = REVOLVING_MAX_LTV) -> dict:
    """Revolving limit permitted by the LTV caps given the amortizing balance."""
    if property_value <= 0 or amortizing_balance < 0:
        raise ValueError("property_value must be positive and balances non-negative")
    if not 0 < revolving_ltv <= combined_ltv <= 100:
        raise ValueError("need 0 < revolving_ltv <= combined_ltv <= 100")
    combined_cap = property_value * combined_ltv / 100
    revolving_cap = property_value * revolving_ltv / 100
    regulatory = max(0.0, min(revolving_cap, combined_cap - amortizing_balance))
    limit = regulatory if authorized_limit is None else min(regulatory, authorized_limit)
    return {"combined_cap": combined_cap, "revolving_cap": revolving_cap, "regulatory_revolving_limit": regulatory,
            "revolving_limit": limit, "bound_by": ("authorized limit" if authorized_limit is not None and authorized_limit < regulatory
                                                   else "65% revolving cap" if regulatory == revolving_cap
                                                   else "80% combined cap" if regulatory > 0 else "no room")}


def readvanceable(property_value: float, amortizing: list[dict], heloc_balance: float, heloc_rate: float, *,
                  authorized_limit: float | None = None, as_of: date | None = None, basis: str = "actual_365",
                  combined_ltv: float = COMBINED_MAX_LTV, revolving_ltv: float = REVOLVING_MAX_LTV,
                  projection_years: int = 0) -> dict:
    """Room, LTVs and minimum payment for a readvanceable plan; optional year-by-year readvance projection.

    ``amortizing``: segments ``{"label", "balance", "rate", "amort_years", "rate_type"}``; rate and
    amort_years are only needed for the projection.
    """
    if heloc_balance < 0:
        raise ValueError("heloc_balance cannot be negative")
    as_of = as_of or date.today()
    amort_total = sum(float(s["balance"]) for s in amortizing)
    lim = limits(property_value, amort_total, authorized_limit, combined_ltv, revolving_ltv)
    available = max(0.0, lim["revolving_limit"] - heloc_balance)
    total = amort_total + heloc_balance
    flags = []
    if heloc_balance > lim["regulatory_revolving_limit"] + 0.005:
        flags.append(f"revolving balance exceeds the permitted revolving limit by "
                     f"${heloc_balance - lim['regulatory_revolving_limit']:,.2f}; the excess would have to amortize")
    if total > lim["combined_cap"] + 0.005:
        flags.append(f"total borrowing is {total / property_value * 100:.1f}% of value, above the {combined_ltv:.0f}% cap")
    if amort_total > lim["revolving_cap"]:
        flags.append(f"amortizing segments are above {revolving_ltv:.0f}% of value: principal repaid on the part above "
                     f"{revolving_ltv:.0f}% reduces the plan limit and is not readvanceable")
    out = {
        "as_of": as_of.isoformat(), "property_value": round(property_value, 2),
        "amortizing_balance": round(amort_total, 2), "heloc_balance": round(heloc_balance, 2),
        "combined_ltv_pct": round(total / property_value * 100, 2),
        "revolving_ltv_pct": round(heloc_balance / property_value * 100, 2),
        "combined_cap": round(lim["combined_cap"], 2), "revolving_cap": round(lim["revolving_cap"], 2),
        "revolving_limit": round(lim["revolving_limit"], 2), "limit_bound_by": lim["bound_by"],
        "available_room": round(available, 2),
        "minimum_payment_interest_only": round(interest_only_payment(heloc_balance, heloc_rate, basis, as_of), 2),
        "interest_basis": basis, "flags": flags, "rule_source": OSFI_SOURCE,
    }
    if projection_years > 0:
        out["projection"] = _project(property_value, amortizing, heloc_balance, authorized_limit, as_of,
                                     projection_years, combined_ltv, revolving_ltv)
    return out


def _project(property_value: float, amortizing: list[dict], heloc_balance: float, authorized_limit: float | None,
             as_of: date, years: int, combined_ltv: float, revolving_ltv: float) -> list[dict]:
    """Year-end revolving limit as the amortizing segments are paid down (value and HELOC balance held flat)."""
    scheds = []
    for s in amortizing:
        if not {"rate", "amort_years"} <= set(s):
            raise ValueError("projection needs rate and amort_years on every amortizing segment")
        first = date(as_of.year + (as_of.month == 12), as_of.month % 12 + 1, 1)
        scheds.append(build(LoanSpec(float(s["balance"]), float(s["rate"]), float(s["amort_years"]), first,
                                     s.get("frequency", "monthly"), s.get("rate_type", "fixed"))))
    out = []
    for y in range(1, min(years, 40) + 1):
        day = date(as_of.year + y, as_of.month, min(as_of.day, 28))
        amort = sum(sc.balance_on(day) for sc in scheds)
        lim = limits(property_value, amort, authorized_limit, combined_ltv, revolving_ltv)
        out.append({"year": y, "date": day.isoformat(), "amortizing_balance": round(amort, 2),
                    "revolving_limit": round(lim["revolving_limit"], 2),
                    "available_room": round(max(0.0, lim["revolving_limit"] - heloc_balance), 2),
                    "bound_by": lim["bound_by"]})
    return out

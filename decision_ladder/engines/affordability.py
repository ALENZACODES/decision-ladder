"""Solvers that answer the broker's real questions after a file fails a rung.

"What is the most this household can borrow?", "How much down payment would make this pass?",
"How much monthly debt has to be paid off?". Each answer is found by bisection on the same
``qualify.qualify`` function that judged the file, so a remediation can never disagree with the test
that produced the decline.
"""
from __future__ import annotations

from typing import Callable

from . import insured, qualify


def _bisect(ok: Callable[[float], bool], lo: float, hi: float, *, want_max: bool, tol: float = 50.0) -> float | None:
    """Largest (or smallest) x in [lo, hi] with ok(x) True, assuming ok is monotone."""
    if want_max:
        if not ok(lo):
            return None
        if ok(hi):
            return hi
        while hi - lo > tol:
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if ok(mid) else (lo, mid)
        return lo
    if not ok(hi):
        return None
    if ok(lo):
        return lo
    while hi - lo > tol:
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    return hi


def _q(file: dict, **over) -> qualify.Qualification:
    f = {**file, **over}
    keys = ("price", "down_payment", "annual_income", "contract_rate", "property_tax_annual", "heat_annual",
            "condo_fees_monthly", "other_debt_monthly", "amort_years", "first_time_buyer", "new_build")
    return qualify.qualify(**{k: f[k] for k in keys if k in f})


def max_purchase_price(file: dict, *, cap: float = 5_000_000) -> dict:
    """Highest price that passes with the file's cash on hand (down payment held constant in dollars).

    Property tax is scaled with price at the file's current tax-to-price ratio."""
    dp = float(file["down_payment"])
    tax_ratio = float(file.get("property_tax_annual", 0.0)) / float(file["price"]) if file.get("price") else 0.0

    def ok(price: float) -> bool:
        if price <= dp:
            return False
        return _q(file, price=price, property_tax_annual=price * tax_ratio).passes

    best = _bisect(ok, dp + 1_000, cap, want_max=True, tol=500)
    if best is None:
        return {"max_price": None, "reason": "no price above the down payment passes with these inputs"}
    best = float(int(best // 1000 * 1000))
    q = _q(file, price=best, property_tax_annual=best * tax_ratio)
    return {"max_price": best, "down_payment": dp, "qualification": q.to_dict(),
            "assumption": "down payment held constant in dollars; property tax scaled with price"}


def min_down_payment_to_pass(file: dict) -> dict:
    price = float(file["price"])
    floor = insured.min_down_payment(price)

    def ok(dp: float) -> bool:
        return _q(file, down_payment=dp).passes

    best = _bisect(ok, floor, price * 0.95, want_max=False, tol=100)
    if best is None:
        return {"min_down_payment": None, "reason": "even 95% down does not pass; income or debt is the binding constraint"}
    best = float(-(-best // 500) * 500)  # round up to $500
    return {"min_down_payment": best, "additional_needed": round(max(0.0, best - float(file["down_payment"])), 2),
            "regulatory_minimum": round(floor, 2), "qualification": _q(file, down_payment=best).to_dict()}


def max_other_debt(file: dict) -> dict:
    """Highest monthly non-housing debt the file can carry and still pass."""
    def ok(debt: float) -> bool:
        return _q(file, other_debt_monthly=debt).passes

    best = _bisect(ok, 0.0, 20_000.0, want_max=True, tol=5)
    if best is None:
        return {"max_other_debt_monthly": None, "reason": "fails even with zero other debt (GDS or down payment)"}
    cur = float(file.get("other_debt_monthly", 0.0))
    best = float(int(best))
    return {"max_other_debt_monthly": best, "current_other_debt_monthly": cur,
            "debt_to_pay_down_monthly": round(max(0.0, cur - best), 2)}


def min_income_to_pass(file: dict) -> dict:
    def ok(inc: float) -> bool:
        return _q(file, annual_income=inc).passes

    best = _bisect(ok, 10_000.0, 5_000_000.0, want_max=False, tol=100)
    if best is None:
        return {"min_annual_income": None, "reason": "fails at any income (down payment, amortization or price cap rule)"}
    best = float(-(-best // 500) * 500)
    return {"min_annual_income": best, "shortfall": round(max(0.0, best - float(file["annual_income"])), 2)}


def remediation_options(file: dict) -> dict:
    """All single-lever fixes, each verified by re-running the qualification."""
    base = _q(file)
    out = {"passes_now": base.passes, "reasons": base.reasons, "options": []}
    if base.passes:
        return out
    for name, fn in (("lower_price", max_purchase_price), ("more_down_payment", min_down_payment_to_pass),
                     ("pay_down_debt", max_other_debt), ("more_income_or_co_borrower", min_income_to_pass)):
        res = fn(file)
        out["options"].append({"lever": name, **res})
    if not file.get("first_time_buyer") and not file.get("new_build") and int(file.get("amort_years", 25)) <= 25:
        q30 = _q(file, amort_years=30)
        out["options"].append({"lever": "30_year_amortization", "passes": q30.passes,
                               "note": "30-year amortization is available uninsured, or insured for first-time buyers / new builds",
                               "qualification": q30.to_dict()})
    return out

"""Solvers on the rental ratio engine: the highest purchase price under each rental method, and the lowest rent
a property needs for the file to pass.

Purchase rules (minimum down payment, amortization limits, the $1.5M insured cap, default-insurance premium,
stressed payment at the qualifying rate) come from ``engines.qualify.qualify``, the same function that judges
an owner-occupied purchase; the GDS/TDS test is replaced by the rental-aware ratios. Searches use the
affordability engine's bisection, so they assume the test is monotone in price (or rent), which it is.
"""
from __future__ import annotations

from ..engines import qualify
from ..engines.affordability import _bisect
from . import params as P
from .rental import METHODS, POLICY_KEYS, Property, as_properties, ratios

OWNER_HEAT_DEFAULT = 1800.0        # same default heat as engines.qualify


def _subject_test(price: float, a: dict, pol: dict, method: str) -> tuple[bool, dict, list[str], qualify.Qualification]:
    dp, owner = float(a["down_payment"]), a["owner_occupied"]
    heat = a["heat_annual"] if a.get("heat_annual") is not None else (OWNER_HEAT_DEFAULT if owner else 0.0)
    tax = price * a["property_tax_rate_pct"] / 100
    q = qualify.qualify(price=price, down_payment=dp, annual_income=max(a["income_annual"], 1.0),
                        contract_rate=a["contract_rate"], property_tax_annual=tax, heat_annual=heat,
                        condo_fees_monthly=a.get("condo_fees_monthly", 0.0), amort_years=a["amort_years"],
                        first_time_buyer=a.get("first_time_buyer", False), new_build=a.get("new_build", False))
    rules = [r for r in q.reasons if not r.startswith(("GDS", "TDS", "principal"))]
    min_eq = P.VERIFIED["rental_min_equity_pct"]["value"]
    if not owner and dp < price * min_eq / 100:
        rules.append(f"non-owner-occupied purchase needs {min_eq:g}% down (${price * min_eq / 100:,.0f})")
    if price <= dp:
        rules.append("price must exceed the down payment")
        return False, {}, rules, q
    subject = Property(name="subject", value=price, balance=q.mortgage_amount, rate=a["contract_rate"],
                       amort_years=a["amort_years"], rent_monthly=a.get("rent_monthly", 0.0), taxes_annual=tax,
                       heat_annual=heat, condo_fees_monthly=a.get("condo_fees_monthly", 0.0),
                       other_expenses_annual=a.get("other_expenses_annual", 0.0), owner_occupied=owner,
                       new_mortgage=True, payment_monthly=q.stressed_payment)
    r = ratios(a["income_annual"], a["existing"] + [subject], method=method,
               other_debt_monthly=a.get("other_debt_monthly", 0.0), policy=pol)
    return (not rules and r["passes"]), r, rules, q


def max_purchase_price(*, income_annual: float, down_payment: float, contract_rate: float, method: str = "all",
                       owner_occupied: bool = True, rent_monthly: float = 0.0, property_tax_rate_pct: float = 1.0,
                       heat_annual: float | None = None, condo_fees_monthly: float = 0.0,
                       other_expenses_annual: float = 0.0, other_debt_monthly: float = 0.0, amort_years: int = 25,
                       first_time_buyer: bool = False, new_build: bool = False, properties=None,
                       policy: dict | None = None, cap: float = 5_000_000) -> dict:
    """Highest price (nearest $1,000 below) that passes, per rental method, with the down payment fixed in dollars."""
    pol = P.policy(policy)
    methods = METHODS if method == "all" else (method,)
    if any(m not in METHODS for m in methods):
        raise ValueError(f"method must be 'all' or one of {METHODS}")
    a = {"income_annual": float(income_annual), "down_payment": float(down_payment), "contract_rate": contract_rate,
         "owner_occupied": owner_occupied, "rent_monthly": rent_monthly, "property_tax_rate_pct": property_tax_rate_pct,
         "heat_annual": heat_annual, "condo_fees_monthly": condo_fees_monthly,
         "other_expenses_annual": other_expenses_annual, "other_debt_monthly": other_debt_monthly,
         "amort_years": amort_years, "first_time_buyer": first_time_buyer, "new_build": new_build,
         "existing": as_properties(properties)}
    results = {}
    for m in methods:
        best = _bisect(lambda p: _subject_test(p, a, pol, m)[0], down_payment + 1_000, cap, want_max=True, tol=250)
        if best is None:
            _, r, rules, _ = _subject_test(down_payment + 1_000, a, pol, m)
            results[m] = {"max_price": None, "reasons": rules + r.get("reasons", [])}
            continue
        best = float(int(best // 1000 * 1000))
        ok, r, _, q = _subject_test(best, a, pol, m)
        results[m] = {"max_price": best, "mortgage_amount": q.mortgage_amount, "insurance_premium": q.insurance_premium,
                      "ltv": q.ltv, "qualifying_rate": q.qualifying_rate, "stressed_payment": q.stressed_payment,
                      "gds": r["gds"], "tds": r["tds"],
                      "binding": "GDS" if qualify.GDS_LIMIT - r["gds"] <= qualify.TDS_LIMIT - r["tds"] else "TDS"}
    priced = {m: v["max_price"] for m, v in results.items() if v["max_price"]}
    keys = sorted({k for m in methods for k in POLICY_KEYS[m]})
    return {"engine": "income.solve.max_purchase_price",
            "method": "bisection on price; purchase rules from engines.qualify, ratios from income.rental",
            "results": results, "best_method": max(priced, key=priced.get) if priced else None,
            "max_price": max(priced.values()) if priced else None, "down_payment": float(down_payment),
            "assumptions": {**P.assumptions(pol, keys),
                            "down_payment": "held constant in dollars",
                            "property_tax": f"{property_tax_rate_pct:g}% of price per year",
                            "heat": "default $1,800/yr owner-occupied, $0 rental (tenant pays) unless given"},
            "source": P.sources("qualifying_rate_floor_pct", "gds_limit_pct", "tds_limit_pct",
                                "subject_rent_addback_max_pct", "rental_min_equity_pct")}


def rent_needed(*, income_annual: float, properties, target: str, other_debt_monthly: float = 0.0,
                policy: dict | None = None, max_rent: float = 50_000) -> dict:
    """Lowest monthly rent on ``target`` that lets the whole file pass GDS and TDS, under each method."""
    pol = P.policy(policy)
    props = as_properties(properties)
    idx = next((i for i, p in enumerate(props) if p.name == target), None)
    if idx is None:
        raise ValueError(f"no property named {target!r}")
    current = props[idx].rent_monthly

    def passes(rent: float, m: str) -> bool:
        trial = list(props)
        trial[idx] = Property(**{**props[idx].__dict__, "rent_monthly": rent})
        return ratios(income_annual, trial, method=m, other_debt_monthly=other_debt_monthly, policy=pol)["passes"]

    out = {}
    for m in METHODS:
        need = _bisect(lambda r: passes(r, m), 0.0, max_rent, want_max=False, tol=0.01)
        need = None if need is None else float(-(-need // 1))   # round up to the dollar
        out[m] = {"min_rent_monthly": need, "current_rent_monthly": current,
                  "shortfall_monthly": None if need is None else round(max(0.0, need - current), 2),
                  "passes_now": passes(current, m)}
    feasible = {m: v["min_rent_monthly"] for m, v in out.items() if v["min_rent_monthly"] is not None}
    return {"engine": "income.solve.rent_needed", "method": "bisection on the target's rent, other inputs fixed",
            "target": target, "results": out,
            "most_forgiving_method": min(feasible, key=feasible.get) if feasible else None,
            "assumptions": P.assumptions(pol, sorted({k for v in POLICY_KEYS.values() for k in v})),
            "source": P.sources("gds_limit_pct", "tds_limit_pct", "qualifying_rate_floor_pct")}

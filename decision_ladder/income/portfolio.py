"""Multi-property investor portfolio: LTV, NOI and DSCR per property, total debt service, and TDS drag.

A property *drags* TDS when the borrower's TDS is higher with it than without it under the chosen rental
method (leave-one-out on the same ratio engine the lender's test uses).
"""
from __future__ import annotations

from . import params as P
from .rental import CONDO_SHARE, as_properties, ratios


def property_metrics(p, vacancy_pct: float, min_dscr: float) -> dict:
    ads = 12 * p.pi_monthly()
    row = {"name": p.name, "value": p.value, "balance": p.balance,
           "ltv_pct": round(p.balance / p.value * 100, 2) if p.value else None,
           "pi_monthly": round(ads / 12, 2), "annual_debt_service": round(ads, 2)}
    if p.owner_occupied:
        return {**row, "noi": None, "dscr": None, "cash_flow_monthly": None, "below_min_dscr": False,
                "note": "owner-occupied: housing cost, not a rental"}
    gross = 12 * p.rent_monthly
    noi = (gross * (1 - vacancy_pct / 100) - p.taxes_annual - p.heat_annual - 12 * p.condo_fees_monthly
           - p.other_expenses_annual)
    dscr = noi / ads if ads else None
    return {**row, "gross_rent_annual": round(gross, 2), "noi": round(noi, 2),
            "dscr": round(dscr, 3) if dscr is not None else None, "cash_flow_monthly": round((noi - ads) / 12, 2),
            "below_min_dscr": dscr is not None and dscr < min_dscr}


def analyze(properties, *, income_annual: float | None = None, other_debt_monthly: float = 0.0,
            method: str = "offset", policy: dict | None = None) -> dict:
    pol = P.policy(policy)
    props = as_properties(properties)
    if not props:
        raise ValueError("at least one property is required")
    rows = [property_metrics(p, pol["vacancy_pct"], pol["min_dscr"]) for p in props]
    value, bal = sum(p.value for p in props), sum(p.balance for p in props)
    rentals = [r for r in rows if r["noi"] is not None]
    noi, ads_r = sum(r["noi"] for r in rentals), sum(r["annual_debt_service"] for r in rentals)
    out = {"engine": "income.portfolio.analyze", "method": method, "properties": rows,
           "portfolio": {"properties": len(props), "rentals": len(rentals), "total_value": round(value, 2),
                         "total_balance": round(bal, 2), "equity": round(value - bal, 2),
                         "ltv_pct": round(bal / value * 100, 2) if value else None,
                         "total_annual_debt_service": round(sum(r["annual_debt_service"] for r in rows), 2),
                         "rental_noi": round(noi, 2),
                         "rental_dscr": round(noi / ads_r, 3) if ads_r else None,
                         "rental_cash_flow_monthly": round((noi - ads_r) / 12, 2)},
           "below_min_dscr": [r["name"] for r in rows if r["below_min_dscr"]],
           "assumptions": {**P.assumptions(pol, ("vacancy_pct", "min_dscr")),
                           "noi": "gross rent less vacancy, taxes, heat, 100% of condo fees and other expenses; "
                                  "debt service is P&I"},
           "source": P.sources("gds_limit_pct", "tds_limit_pct", "condo_fee_pct")}
    if income_annual is None:
        return out
    base = ratios(income_annual, props, method=method, other_debt_monthly=other_debt_monthly, policy=pol)
    drag = []
    for i, p in enumerate(props):
        without = ratios(income_annual, props[:i] + props[i + 1:], method=method,
                         other_debt_monthly=other_debt_monthly, policy=pol)
        delta = None if base["tds"] is None or without["tds"] is None else round(base["tds"] - without["tds"], 2)
        drag.append({"name": p.name, "tds_with": base["tds"], "tds_without": without["tds"],
                     "tds_impact_pts": delta, "drags_tds": delta is not None and delta > 0})
    drag.sort(key=lambda d: -(d["tds_impact_pts"] or 0))
    out.update({"ratios": base, "tds_drag": drag, "drags_tds": [d["name"] for d in drag if d["drags_tds"]]})
    out["assumptions"].update(P.assumptions(pol, ("offset_pct", "addback_pct")))
    out["assumptions"]["condo_share_in_ratios"] = f"{CONDO_SHARE:.0%} of condo fees in GDS/TDS (CMHC)"
    return out

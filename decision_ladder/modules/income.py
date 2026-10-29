"""Income & Rental Qualification Desk tools, registered like the Business Lending Desk: native code with its UI
at ``/desks/income.html``, no AppModule, and lifecycle stages given in the router's core map."""
from __future__ import annotations

from ..agent import router
from ..agent.tools import Tool, _obj
from ..income import params as P, portfolio, rental, solve, sources
from .registry import add_tool

N, I, B, S = {"type": "number"}, {"type": "integer"}, {"type": "boolean"}, {"type": "string"}


def _d(t: dict, desc: str) -> dict:
    return {**t, "description": desc}


SOURCE = _obj({
    "type": {"type": "string", "enum": sorted(sources.TYPES)},
    "label": S,
    "annual_amount": _d(N, "dollars per year (salary, pension, CPP/OAS, support, CCB)"),
    "hourly_rate": _d(N, "dollars per hour"), "guaranteed_hours_per_week": N,
    "history": {"type": "array", "items": N, "description": "overtime/bonus/commission/contract by year, oldest first"},
    "years": {"type": "array", "description": "self-employed years, oldest first, dollars",
              "items": _obj({"net_income": _d(N, "T2125 / line 15000 net"), "cca": N, "business_use_of_home": N,
                             "other_add_backs": N}, ["net_income"])},
    "income_method": {"type": "string", "enum": ["add_backs", "gross_up"]},
    "gross_up_pct": _d(N, "self-employed gross-up percent; CMHC 15, higher is lender-specific (Alt-A/BFS)"),
    "months_in_business": I, "court_order": B, "years_remaining": N, "probation": B, "nontaxable": B,
    "months_remaining": _d(I, "contract months left"),
}, ["type"])
PROPERTY = _obj({
    "name": S, "value": _d(N, "dollars"), "balance": _d(N, "mortgage balance, dollars"),
    "rate": _d(N, "contract rate, percent"), "amort_years": _d(N, "remaining amortization, years"),
    "rent_monthly": _d(N, "gross rent, dollars per month"), "taxes_annual": N,
    "heat_annual": _d(N, "0 if tenant pays"), "condo_fees_monthly": N,
    "other_expenses_annual": _d(N, "insurance, repairs, management, dollars per year"),
    "owner_occupied": B, "new_mortgage": _d(B, "stress-test this mortgage at the B-20 qualifying rate"),
    "payment_monthly": _d(N, "actual P&I if known"), "t776_net_income": _d(N, "T776 net rental income, dollars"),
    "cca_claimed": N, "mortgage_interest_annual": N,
})
POLICY = _obj({k: ({"type": "boolean"} if isinstance(v, bool) else N) | {"description": f"{d} - lender policy"}
               for k, (v, d) in P.LENDER_POLICY.items()})
PROPS = {"type": "array", "items": PROPERTY}
INCOME = {"annual_income": _d(N, "qualifying income, dollars per year (or give income_sources)"),
          "income_sources": {"type": "array", "items": SOURCE}, "policy": POLICY,
          "other_debt_monthly": _d(N, "non-property debt payments, dollars per month")}
METHOD = {"type": "string", "enum": list(rental.METHODS)}


def _income(a: dict) -> tuple[float, dict | None]:
    if a.get("income_sources"):
        q = sources.qualifying_income(a["income_sources"], a.get("policy"))
        return q["total_qualifying_annual"], q
    if a.get("annual_income") is None:
        raise ValueError("give annual_income or income_sources")
    return float(a["annual_income"]), None


def _with_income(out: dict, detail: dict | None) -> dict:
    if detail:
        out["income"] = {k: detail[k] for k in ("total_qualifying_annual", "sources", "flags")}
    return out


def t_income(a: dict) -> dict:
    return sources.qualifying_income(a["income_sources"], a.get("policy"))


def t_compare(a: dict) -> dict:
    inc, detail = _income(a)
    return _with_income(rental.compare_methods(inc, a["properties"], other_debt_monthly=a.get("other_debt_monthly", 0.0),
                                               policy=a.get("policy")), detail)


def t_portfolio(a: dict) -> dict:
    inc, detail = _income(a) if a.get("income_sources") or a.get("annual_income") is not None else (None, None)
    return _with_income(portfolio.analyze(a["properties"], income_annual=inc, method=a.get("method", "offset"),
                                          other_debt_monthly=a.get("other_debt_monthly", 0.0),
                                          policy=a.get("policy")), detail)


def t_max_price(a: dict) -> dict:
    a = dict(a)
    inc, detail = _income(a)
    for k in ("annual_income", "income_sources"):
        a.pop(k, None)
    return _with_income(solve.max_purchase_price(income_annual=inc, **a), detail)


def t_rent_needed(a: dict) -> dict:
    inc, detail = _income(a)
    return _with_income(solve.rent_needed(income_annual=inc, properties=a["properties"], target=a["target"],
                                          other_debt_monthly=a.get("other_debt_monthly", 0.0),
                                          policy=a.get("policy")), detail)


def t_policy(a: dict) -> dict:
    return {"engine": "income.params", "method": "reference", "verified": P.VERIFIED,
            "lender_policy_defaults": {k: {"default": v, "description": d, "status": "lender policy, varies"}
                                       for k, (v, d) in P.LENDER_POLICY.items()},
            "source": P.sources(*P.VERIFIED)}


TOOLS = [
    Tool("income_qualifying",
         "Qualifying income by source as Canadian lenders treat it: salary, hourly (guaranteed hours x rate x 52), "
         "overtime/bonus/commission/contract (2-year average, the lower recent year if declining), self-employed "
         "(2-year T2125 net plus CCA and business-use-of-home add-backs, or a gross-up: CMHC 15%, higher is "
         "lender-specific), pension, CPP/OAS, child/spousal support (court order), CCB (lender-dependent). Returns "
         "dollars per year per source with method, documents and flags.",
         _obj({"income_sources": {"type": "array", "items": SOURCE}, "policy": POLICY}, ["income_sources"]),
         t_income, "underwriting"),
    Tool("rental_method_compare",
         "GDS and TDS (percent) for the same borrower and properties under the add-back, offset and net-rental "
         "methods at the B-20 qualifying rate and CMHC 39/44 limits, and which method leaves the most housing payment "
         "room (dollars per month). Add-back/offset percentages are lender policy parameters.",
         _obj({**INCOME, "properties": PROPS}, ["properties"]), t_compare, "underwriting"),
    Tool("rental_portfolio",
         "Investor portfolio: LTV (percent) per property and overall, NOI, DSCR and cash flow per rental, total annual "
         "debt service (dollars), and, with income, which properties drag TDS (percentage points, leave-one-out) "
         "under the chosen rental method.",
         _obj({**INCOME, "properties": PROPS, "method": METHOD}, ["properties"]), t_portfolio, "underwriting"),
    Tool("income_max_purchase",
         "Maximum purchase price (dollars) with a fixed down payment, counting the subject property's rent and the "
         "borrower's existing rentals under each rental method (or one). Uses the B-20 stress test, insured "
         "down-payment and amortization rules, CMHC premium, and 20% down for non-owner-occupied purchases.",
         _obj({**INCOME, "down_payment": _d(N, "dollars"), "contract_rate": _d(N, "percent"),
               "method": {"type": "string", "enum": ["all", *rental.METHODS]},
               "owner_occupied": B, "rent_monthly": _d(N, "subject property gross rent, dollars per month"),
               "property_tax_rate_pct": _d(N, "annual property tax as percent of price, default 1.0"),
               "heat_annual": N, "condo_fees_monthly": N, "other_expenses_annual": N, "amort_years": I,
               "first_time_buyer": B, "new_build": B, "properties": PROPS},
              ["down_payment", "contract_rate"]), t_max_price, "underwriting"),
    Tool("rental_rent_needed",
         "Lowest monthly rent (dollars) a named property needs for the borrower's whole file to pass GDS/TDS, under "
         "each rental method, with the shortfall against the current rent.",
         _obj({**INCOME, "properties": PROPS, "target": _d(S, "name of the property to solve for")},
              ["properties", "target"]), t_rent_needed, "underwriting"),
    Tool("income_policy_reference",
         "The regulatory figures the income desk uses (B-20 qualifying rate, CMHC GDS/TDS, rental and self-employed "
         "rules) with source URLs and check dates, and the lender-policy defaults that vary by lender.",
         _obj({}), t_policy, "underwriting"),
]

for _t in TOOLS:
    add_tool(_t, None)
    router.CORE_STAGE.setdefault(_t.name, ["prequal", "underwriting"])

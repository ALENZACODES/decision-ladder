"""Business Lending Desk tools: CSBFP, invoice factoring, unsecured credit, DSCR capacity, lease versus buy.

Registered with :func:`add_tool` only. The registry's :class:`AppModule` describes a vendored project under
``modules/<dir>/``; the desk is native code with its UI at ``/desks/business.html``, so no AppModule is added.
Because the router learns module tools' stages from AppModules, the desk's tools are given their lifecycle
stages in the router's core map instead, so the copilot can route to them.
"""
from __future__ import annotations

from ..agent import router
from ..agent.tools import Tool, _obj
from ..business import capacity, csbfp, factoring, lease, unsecured, usury
from .registry import add_tool

N, I, B, S = {"type": "number"}, {"type": "integer"}, {"type": "boolean"}, {"type": "string"}


def _d(t: dict, desc: str) -> dict:
    return {**t, "description": desc}


BORROWER = {"borrower_is_natural_person": _d(B, "true if the borrower is an individual (sole proprietor); default false"),
            "business_purpose": _d(B, "credit is for a business purpose; default true")}
FACTOR_TERMS = {
    "advance_rate_pct": _d(N, "percent of face advanced, e.g. 85"),
    "fee_type": {"type": "string", "enum": ["flat", "per_period", "tiered"]},
    "fee_pct": _d(N, "percent: flat fee, fee per period, or per extra period past the last tier"),
    "period_days": _d(I, "days per fee period, default 30"),
    "tiers": {"type": "array", "description": "cumulative fee by days outstanding",
              "items": _obj({"up_to_days": I, "fee_pct": N}, ["up_to_days", "fee_pct"])},
    "prorate": _d(B, "pro-rate per-period fees by day instead of charging each started period"),
    "fee_basis": {"type": "string", "enum": ["face", "advance"]},
    "recourse": _d(B, "true = client repurchases unpaid invoices at recourse_days"),
    "recourse_days": _d(I, "days after which an unpaid invoice is put back to the client, default 90"),
    "non_recourse_premium_pct": _d(N, "extra percent of face charged for non-recourse"),
    "upfront_fees": _d(N, "dollars per invoice deducted at funding"),
}
CAPACITY_PROPS = {
    "net_income": _d(N, "net income, dollars per year"),
    "existing_business_debt_service": _d(N, "existing business principal + interest, dollars per year"),
    "interest_expense": N, "income_taxes": N, "depreciation_amortization": N,
    "add_backs": {"type": "array", "description": "one-time items added back (negative = deduction), dollars",
                  "items": _obj({"label": S, "amount": N}, ["amount"])},
    "owner_compensation_paid": _d(N, "owner salary/bonus in expenses, dollars per year"),
    "market_compensation": _d(N, "market salary for the owner's role, dollars per year"),
    "unfunded_capex": N, "cash_taxes": N, "distributions": _d(N, "dividends/draws beyond market salary, dollars per year"),
    "proposed_loan": _obj({"amount": N, "annual_rate_pct": N, "amort_years": N}, ["amount", "annual_rate_pct", "amort_years"]),
    "target_dscr": _d(N, "default 1.25"), "new_loan_rate_pct": N, "new_loan_amort_years": N,
    "owner": _obj({"personal_income": N, "personal_taxes": N, "living_expenses": N, "personal_debt_service": N}),
    "target_global_dscr": N,
}


def t_csbfp_assess(a: dict) -> dict:
    return csbfp.assess(a["gross_annual_revenue"], a.get("request", {}), a.get("farming", False),
                        a.get("existing_term_outstanding", 0.0), a.get("existing_loc_authorized", 0.0))


def t_csbfp_loan(a: dict) -> dict:
    return csbfp.term_loan(**a)


def t_csbfp_loc(a: dict) -> dict:
    return csbfp.line_of_credit(**a)


def t_factor(a: dict) -> dict:
    a = dict(a)
    invoices = a.pop("invoices", None)
    adv = a.pop("advance_rate_pct")
    if invoices:
        a.pop("face", None), a.pop("days_to_collect", None)
        return factoring.factor_ledger(invoices, adv, **a)
    if "face" not in a or "days_to_collect" not in a:
        raise ValueError("give face and days_to_collect, or invoices")
    return factoring.factor_invoice(a.pop("face"), adv, a.pop("days_to_collect"), **a)


def t_term_loan(a: dict) -> dict:
    return unsecured.term_loan(**a)


def t_loc(a: dict) -> dict:
    return unsecured.line_of_credit(**a)


def t_mca(a: dict) -> dict:
    return unsecured.merchant_cash_advance(**a)


def t_criminal(a: dict) -> dict:
    out = usury.check(**a)
    out["engine"] = "business.usury.check"
    return out


def t_dscr(a: dict) -> dict:
    return capacity.dscr(**a)


def t_lease(a: dict) -> dict:
    return lease.lease_vs_buy(**a)


TOOLS = [
    Tool("csbfp_assess",
         "Canada Small Business Financing Program screen: revenue-cap eligibility, eligible amounts by class (dollars: "
         "real_property, equipment, leasehold_improvements, intangible_assets, working_capital, line_of_credit) after the "
         "$500k equipment+leasehold, $150k intangibles+working capital, $1M term and $1.15M borrower limits, and 2% "
         "registration fees. Parameters verified on ised-isde.canada.ca with dates.",
         _obj({"gross_annual_revenue": _d(N, "dollars per year"), "farming": B,
               "request": _obj({k: N for k in csbfp.TERM_CLASSES + ("line_of_credit",)}),
               "existing_term_outstanding": _d(N, "existing CSBFP term loans of borrower and related borrowers, dollars"),
               "existing_loc_authorized": N}, ["gross_annual_revenue", "request"]), t_csbfp_assess, "business"),
    Tool("csbfp_term_loan",
         "CSBFP term loan cost: monthly payment, 2% registration fee (financed or paid), all-in APR/EAR (percent), the "
         "program maximum rate (floating: prime+3; fixed: lender residential rate+3) and the 1.25% admin fee the lender "
         "remits on month-end balances. Rates in percent, years <= 15.",
         _obj({"amount": _d(N, "dollars"), "annual_rate_pct": N, "years": N,
               "rate_kind": {"type": "string", "enum": ["floating", "fixed"]}, "prime_pct": N, "residential_rate_pct": N,
               "finance_registration_fee": B, "other_fees": _d(N, "dollars deducted at funding")},
              ["amount", "annual_rate_pct", "years"]), t_csbfp_loan, "business"),
    Tool("csbfp_line_of_credit",
         "CSBFP line of credit (max $150,000, up to 5 years): program maximum rate (prime + 5, percent), 2% registration "
         "fee on the authorized amount spread over the years, and annual cost and APR (percent) on the average drawn balance.",
         _obj({"authorized": _d(N, "dollars"), "average_drawn": _d(N, "dollars"), "annual_rate_pct": N, "prime_pct": N,
               "years": _d(N, "registration period, max 5"), "standby_fee_pct": N},
              ["authorized", "average_drawn", "annual_rate_pct", "prime_pct"]), t_csbfp_loc, "business"),
    Tool("invoice_factoring",
         "Invoice factoring cost: advance, discount fee (flat, per period e.g. per 30 days, or tiered), reserve release, "
         "recourse repurchase or non-recourse premium, and effective cost as APR and EAR (percent) from the day-count of "
         "the cash. One invoice (face dollars, days_to_collect) or a ledger (invoices: [{face, days_to_collect}]).",
         _obj({"face": N, "days_to_collect": N,
               "invoices": {"type": "array", "items": _obj({"face": N, "days_to_collect": N}, ["face", "days_to_collect"])},
               **FACTOR_TERMS}, ["advance_rate_pct"]), t_factor, "business"),
    Tool("unsecured_term_loan",
         "Unsecured business term loan: level payment, total cost of credit, APR and EAR (percent) with upfront and financed "
         "fees in the rate, and the Criminal Code criminal-rate check (35% APR; 48% for business loans to non-individuals "
         "over $10k to $500k; none above $500k).",
         _obj({"principal": _d(N, "dollars"), "annual_rate_pct": N, "years": N, "payments_per_year": I,
               "upfront_fees": _d(N, "dollars deducted from the advance"), "financed_fees": _d(N, "dollars added to the loan"),
               **BORROWER}, ["principal", "annual_rate_pct", "years"]), t_term_loan, "business"),
    Tool("business_line_of_credit",
         "Business line of credit annual cost on the average drawn balance: interest, standby fee on undrawn (percent), "
         "annual and setup fees; effective cost and APR (percent) with the criminal-rate check.",
         _obj({"limit": N, "average_drawn": N, "annual_rate_pct": N, "standby_fee_pct": N, "annual_fee": N, "setup_fee": N,
               "expected_years": N, **BORROWER}, ["limit", "average_drawn", "annual_rate_pct"]), t_loc, "business"),
    Tool("merchant_cash_advance",
         "Merchant cash advance implied cost: factor rate x advance repaid by daily remittances (holdback percent of expected "
         "daily sales, or expected remittance days), business days per week, fees. Returns APR and EAR (percent) from the "
         "dated flows, a remittance-days sensitivity, and the criminal-rate check.",
         _obj({"advance": _d(N, "dollars"), "factor_rate": _d(N, "e.g. 1.35"), "holdback_pct": N,
               "expected_daily_sales": _d(N, "dollars per remittance day"), "expected_remittance_days": I, "fees": N,
               "days_per_week": I, "sensitivity_days": {"type": "array", "items": I}, **BORROWER},
              ["advance", "factor_rate"]), t_mca, "business"),
    Tool("criminal_rate_check",
         "Is an all-in APR (percent) above Canada's criminal interest rate? Applies 35% APR (from 2025-01-01), the 48% band "
         "for business-purpose credit to non-individuals over $10,000 to $500,000, and no cap above $500,000 (credit advanced, dollars).",
         _obj({"apr_pct": N, "credit_advanced": N, **BORROWER, "pawn": B, "on": _d(S, "agreement date YYYY-MM-DD")},
              ["apr_pct", "credit_advanced"]), t_criminal, "business"),
    Tool("business_dscr",
         "Business borrower capacity: EBITDA with add-backs and owner-pay normalization, cash available for debt service, "
         "DSCR existing and pro forma, global DSCR with the owner's personal income and debts, and the maximum new loan "
         "(dollars) at the target DSCR. All amounts annual dollars.",
         _obj(CAPACITY_PROPS, ["net_income", "existing_business_debt_service"]), t_dscr, "business"),
    Tool("equipment_lease_vs_buy",
         "Equipment lease versus buy with a loan: after-tax NPV at the after-tax borrowing rate, CCA tax shield (class "
         "rate percent; half-year rule or AII/RII first-year factor from acquisition and available-for-use dates), "
         "salvage, net advantage to leasing (dollars, positive = lease) and break-even lease payment.",
         _obj({"cost": _d(N, "dollars"), "lease_payment": _d(N, "dollars per period"), "lease_term_years": I,
               "borrow_rate_pct": N, "tax_rate_pct": N, "cca_rate_pct": _d(N, "class rate, e.g. 20 for class 8"),
               "salvage_value": N, "lease_payments_per_year": I, "lease_in_advance": B, "lease_upfront_fees": N,
               "buy_annual_operating_cost": N, "first_year_factor_override": N,
               "acquired": _d(S, "YYYY-MM-DD"), "available_for_use": _d(S, "YYYY-MM-DD")},
              ["cost", "lease_payment", "lease_term_years", "borrow_rate_pct", "tax_rate_pct", "cca_rate_pct"]),
         t_lease, "business"),
]

STAGES = {"business_dscr": ["commercial", "underwriting"], "criminal_rate_check": ["commercial", "compliance"]}

for _t in TOOLS:
    add_tool(_t, None)
    router.CORE_STAGE.setdefault(_t.name, STAGES.get(_t.name, ["commercial"]))

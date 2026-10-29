"""Commercial Lending Desk tools: CMHC MLI Select / Standard, conventional sizing, construction draws, private
bridge cost and rent roll analysis, wrapping :mod:`decision_ladder.commercial`.

No :class:`AppModule` is registered: the desk has no vendored project under ``modules/`` (``add_module`` would
list it as not present). Its UI is the static page ``/static/desks/commercial.html``. The tools are given the
"commercial" stage in the router's core map so the copilot offers them for commercial questions; the Private
Credit Deal Screener grades a loan once it has been sized here.
"""
from __future__ import annotations

from ..agent.tools import Tool, _obj
from ..commercial import bridge, cmhc, construction, rentroll, underwriting
from ..agent import router
from .registry import add_tool

N, I, B, S = {"type": "number"}, {"type": "integer"}, {"type": "boolean"}, {"type": "string"}


def d(desc: str, base: dict = N) -> dict:
    return {**base, "description": desc}


COMPOUNDING = {"type": "string", "enum": ["semi", "monthly"],
               "description": "semi = fixed rate, semi-annual (Interest Act s.6); monthly = floating"}
LEASE = _obj({"tenant": S, "area": d("rentable square feet"), "rent": d("in-place annual base rent, dollars"),
              "market_rent": d("annual market rent for the space, dollars"), "expiry": d("lease expiry YYYY-MM-DD", S),
              "vacant": B})
RENT_ROLL = {"type": "array", "items": LEASE, "description": "one row per lease or unit"}


def t_underwrite(a: dict) -> dict:
    return underwriting.underwrite(a)


def t_mli(a: dict) -> dict:
    return cmhc.size(**a)


def t_mli_points(a: dict) -> dict:
    out = cmhc.score(**a)
    out["sources"] = cmhc.SOURCES
    out["assumptions"] = ["the 20-year commitment bonus is applied only when affordability points are earned"]
    out["engine"] = "commercial.cmhc"
    return out


def t_construction(a: dict) -> dict:
    return construction.schedule(**a)


def t_bridge(a: dict) -> dict:
    return bridge.cost(**a)


def t_rent_roll(a: dict) -> dict:
    return rentroll.analyze(a["leases"], a["as_of"], a.get("rollover_flag_pct", rentroll.ROLLOVER_FLAG_PCT))


SIZING_PROPS = {
    "contract_rate": d("contract rate, percent"), "value": d("appraised value, dollars"),
    "cap_rate_pct": d("cap rate in percent, used for value when value is omitted"),
    "amort_years": d("amortization, years (default 25)"), "term_years": d("term, years (default 5)"),
    "ltv_max_pct": d("lender LTV cap, percent (default 75)"), "dscr_min": d("minimum DSCR, x (default 1.25)"),
    "debt_yield_min_pct": d("minimum debt yield, percent (default 8; 0 = not tested)"),
    "qualifying_rate": d("rate the lender sizes DSCR at, percent (default contract rate)"),
    "interest_only": B, "compounding": COMPOUNDING, "requested_loan": d("loan asked for, dollars"),
}
INCOME_PROPS = {
    "noi": d("net operating income, dollars per year (skips the income build)"),
    "gross_potential_rent": d("gross potential rent, dollars per year"),
    "other_income": d("parking, laundry etc., dollars per year"), "vacancy_pct": d("vacancy and credit loss, percent of GPR"),
    "expense_ratio_pct": d("operating expenses, percent of effective gross income"),
    "expenses": {"type": "object", "additionalProperties": N, "description": "itemized annual expenses, dollars"},
    "management_pct": d("management fee, percent of EGI"), "reserves_per_unit": d("replacement reserve, dollars per unit per year"),
    "units": I, "rent_roll": RENT_ROLL, "as_of": d("rent roll date YYYY-MM-DD", S),
}
MLI_SCORE_PROPS = {
    "purpose": {"type": "string", "enum": ["existing", "new_construction"]},
    "affordable_units_pct": d("percent of units with rent at or below 30% of median renter income"),
    "affordability_years": d("affordability commitment, years (10 minimum, 20+ earns 30 bonus points)", I),
    "energy_reduction_pct": d("existing: percent energy reduction vs current; new: percent better than NECB/NBC Tier 1"),
    "energy_standard": {"type": "string", "enum": ["necb", "nbc"]},
    "accessibility": {"type": "string", "enum": ["none", "level_1", "level_2"]},
}
BUDGET_LINE = _obj({"item": S, "cost": d("dollars"), "start_month": I, "end_month": I,
                    "hard": d("hard cost subject to holdback (default true)", B)}, ["cost", "start_month"])

for tool in [
    Tool("commercial_underwrite",
         "Conventional commercial mortgage sizing. Builds NOI (GPR - vacancy + other income - expense ratio or itemized "
         "expenses, management, reserves) or takes noi / a rent roll, then max loan = min(LTV cap x value, DSCR loan at "
         "the qualifying rate, NOI / min debt yield) and names the binding constraint. Returns payment, DSCR, debt yield, "
         "LTV, balance at term end, NOI cushion and the highest rate that still meets DSCR. Rates and ratios in percent, "
         "money in dollars per year.",
         _obj({**INCOME_PROPS, **SIZING_PROPS}, ["contract_rate"]), t_underwrite, "commercial"),
    Tool("cmhc_mli_size",
         "CMHC multi-unit (5+ units) insured loan: MLI Standard vs MLI Select side by side. Scores Select points "
         "(affordability, energy, accessibility), maps the tier to max LTV/LTC, amortization, recourse and premium "
         "discount, sizes each by LTV/LTC cap and DCR (1.10 Select, 1.20 Standard), adds the premium, and says which "
         "gives more proceeds. value = lending value (existing) or total project cost (new_construction); noi dollars "
         "per year; rate percent.",
         _obj({**MLI_SCORE_PROPS, "noi": N, "value": N, "rate": d("underwriting rate, percent"), "units": I,
               "amort_years": d("requested amortization, years (capped by program)"),
               "shelter": {"type": "string", "enum": ["standard_rental", "other_shelter"]},
               "compounding": COMPOUNDING, "requested_loan": d("base loan asked for, dollars")},
              ["noi", "value", "rate", "units"]), t_mli, "commercial"),
    Tool("cmhc_mli_select_points",
         "MLI Select points only: points per category, total, the tier reached and what it unlocks, and points needed "
         "for the next tier.",
         _obj(MLI_SCORE_PROPS), t_mli_points, "commercial"),
    Tool("construction_draw_schedule",
         "Construction loan draw schedule by month from a cost budget (each line spread over its months). Applies the "
         "Ontario Construction Act 10% holdback to hard costs with annual release (contracts from 2026-01-01) or release "
         "at completion, funds equity first, accrues interest monthly on the drawn balance into an interest reserve, and "
         "checks LTC (and LTV on completion). Returns loan amount, interest reserve, LTC, and equity needed to meet max "
         "LTC. Money in dollars, rates percent, months from 1 (month 0 = closing).",
         _obj({"budget": {"type": "array", "items": BUDGET_LINE}, "rate_pct": d("construction rate, percent"),
               "equity": d("equity available, dollars"), "land_cost": N, "lender_fee": d("dollars, paid at closing"),
               "term_months": I, "max_ltc_pct": d("percent (default 75)"), "completed_value": N, "max_ltv_pct": N,
               "holdback_pct": d("percent (default 10)"), "release_lag_months": I, "annual_release": B,
               "include_rows": B}, ["budget", "rate_pct", "equity"]), t_construction, "commercial"),
    Tool("private_bridge_cost",
         "Private / bridge first or second mortgage, interest-only: fees, net advance, monthly interest, total cost of "
         "borrowing, effective annual cost and APR from the IRR of the borrower's cash flows (fees, prepaid interest, "
         "exit fee, minimum-interest months), lender yield, cost if repaid early, combined LTV, and an indicative "
         "Criminal Code s.347 rate screen. Rates and fees in percent, money in dollars.",
         _obj({"loan": N, "rate_pct": N, "term_months": I, "lender_fee_pct": N, "broker_fee_pct": N,
               "other_costs": d("legal, appraisal, admin, dollars"), "prepaid_interest_months": I,
               "exit_fee_pct": N, "min_interest_months": I, "compounding": COMPOUNDING, "value": N,
               "prior_balance": d("mortgages ranking ahead, dollars"), "natural_person": B, "business_purpose": B},
              ["loan", "rate_pct", "term_months"]), t_bridge, "commercial"),
    Tool("rent_roll_analysis",
         "Rent roll: physical and economic occupancy, WALT (by rent and by area), lease rollover by year with "
         "concentration flags, largest tenant share, and mark-to-market gap of in-place vs market rent. Rents annual, "
         "dollars.",
         _obj({"leases": RENT_ROLL, "as_of": d("YYYY-MM-DD", S), "rollover_flag_pct": N}, ["leases", "as_of"]),
         t_rent_roll, "commercial"),
]:
    add_tool(tool, None)
    router.CORE_STAGE.setdefault(tool.name, ["commercial"])

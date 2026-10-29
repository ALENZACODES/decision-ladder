"""Conventional (uninsured) commercial mortgage underwriting: NOI and loan sizing.

Max loan = min(LTV cap x value, DSCR-constrained loan at the qualifying rate, debt-yield-constrained loan).
The binding constraint is reported so the broker knows which lever moves the number: more value (LTV),
more NOI or a lower qualifying rate (DSCR), or more NOI only (debt yield).

Default thresholds are typical Canadian conventional lender screens, NOT any one lender's policy. They are
inputs: change them to the lender's term sheet.
"""
from __future__ import annotations

from ..engines import payments
from .common import debt_constant, loan_for_debt_service, monthly_payment, pct, positive, r2, ratio

DEFAULTS = {"ltv_max_pct": 75.0, "dscr_min": 1.25, "debt_yield_min_pct": 8.0, "amort_years": 25.0, "term_years": 5.0}
ASSUMPTIONS = [
    "LTV 75%, DSCR 1.25x and debt yield 8% are typical conventional screens (assumption, set per lender term sheet)",
    "fixed rates compound semi-annually (Interest Act s.6); pass compounding='monthly' for a floating loan",
    "DSCR sizing uses the qualifying rate when given, otherwise the contract rate",
]


def noi(*, gross_potential_rent: float, other_income: float = 0.0, vacancy_pct: float = 5.0,
        expense_ratio_pct: float | None = None, expenses: dict | None = None, management_pct: float = 0.0,
        reserves_per_unit: float = 0.0, units: int = 0) -> dict:
    """Net operating income from potential rent, vacancy and either an expense ratio or itemized expenses."""
    gpr = positive("gross_potential_rent", gross_potential_rent)
    other = positive("other_income", other_income, allow_zero=True)
    vac = gpr * ratio("vacancy_pct", vacancy_pct) / 100
    egi = gpr - vac + other
    lines: dict[str, float] = {}
    if expenses:
        for k, v in expenses.items():
            lines[str(k)] = positive(f"expense {k}", v, allow_zero=True)
    elif expense_ratio_pct is not None:
        lines["operating expenses ({:g}% of EGI)".format(expense_ratio_pct)] = egi * ratio("expense_ratio_pct", expense_ratio_pct) / 100
    else:
        raise ValueError("give either expense_ratio_pct or itemized expenses")
    if management_pct:
        lines["management ({:g}% of EGI)".format(management_pct)] = egi * ratio("management_pct", management_pct) / 100
    if reserves_per_unit:
        lines["replacement reserve"] = positive("reserves_per_unit", reserves_per_unit) * max(0, int(units))
    opex = sum(lines.values())
    return {"gross_potential_rent": r2(gpr), "vacancy_loss": r2(vac), "other_income": r2(other),
            "effective_gross_income": r2(egi), "expenses": {k: r2(v) for k, v in lines.items()},
            "total_expenses": r2(opex), "expense_ratio_pct": pct(opex / egi) if egi else None, "noi": r2(egi - opex)}


def _max_rate_for(loan: float, noi_: float, dscr: float, amort: float, io: bool, comp: str) -> float | None:
    """Highest contract rate (percent) at which ``loan`` still covers ``dscr``; None if it fails even at 0%."""
    def ok(rate: float) -> bool:
        return noi_ >= dscr * monthly_payment(loan, rate, amort, io, comp) * 12
    if not ok(0.0):
        return None
    lo, hi = 0.0, 50.0
    if ok(hi):
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return round(lo, 3)


def size_loan(*, noi: float, contract_rate: float, value: float | None = None, cap_rate_pct: float | None = None,
              amort_years: float = DEFAULTS["amort_years"], term_years: float = DEFAULTS["term_years"],
              ltv_max_pct: float = DEFAULTS["ltv_max_pct"], dscr_min: float = DEFAULTS["dscr_min"],
              debt_yield_min_pct: float = DEFAULTS["debt_yield_min_pct"], qualifying_rate: float | None = None,
              interest_only: bool = False, compounding: str = "semi", requested_loan: float | None = None) -> dict:
    noi_ = positive("noi", noi)
    if value is None:
        if not cap_rate_pct:
            raise ValueError("give value or cap_rate_pct")
        value = noi_ / (positive("cap_rate_pct", cap_rate_pct) / 100)
    value = positive("value", value)
    positive("dscr_min", dscr_min)
    qrate = contract_rate if qualifying_rate is None else qualifying_rate
    constraints = {
        "ltv": value * ratio("ltv_max_pct", ltv_max_pct) / 100,
        "dscr": loan_for_debt_service(noi_ / dscr_min, qrate, amort_years, interest_only, compounding),
    }
    if debt_yield_min_pct:
        constraints["debt_yield"] = noi_ / (positive("debt_yield_min_pct", debt_yield_min_pct) / 100)
    binding = min(constraints, key=constraints.get)
    max_loan = constraints[binding]
    loan = max_loan if requested_loan is None else positive("requested_loan", requested_loan)

    ads = monthly_payment(loan, contract_rate, amort_years, interest_only, compounding) * 12
    ads_q = loan * debt_constant(qrate, amort_years, interest_only, compounding)
    months = round(term_years * 12)
    balloon = loan if interest_only else payments.balance_after(loan, contract_rate, amort_years, months, compounding)
    out = {
        "value": r2(value), "noi": r2(noi_), "cap_rate_pct": pct(noi_ / value),
        "constraints": {k: r2(v) for k, v in constraints.items()},
        "binding_constraint": binding,
        "max_loan": r2(max_loan),
        "loan": r2(loan),
        "monthly_payment": r2(ads / 12), "annual_debt_service": r2(ads),
        "ltv_pct": pct(loan / value), "dscr": round(noi_ / ads, 3) if ads else None,
        "dscr_at_qualifying_rate": round(noi_ / ads_q, 3) if ads_q else None,
        "debt_yield_pct": pct(noi_ / loan) if loan else None,
        "balance_at_term_end": r2(balloon), "term_years": term_years,
        "payment_type": "interest only" if interest_only else f"amortizing over {amort_years:g} years",
        "compounding": compounding, "qualifying_rate": qrate,
        "noi_cushion_pct": pct(1 - ads / noi_) if ads else None,
        "max_rate_meeting_dscr_pct": _max_rate_for(loan, noi_, dscr_min, amort_years, interest_only, compounding),
    }
    if requested_loan is not None:
        out["requested_fits"] = loan <= max_loan + 0.005
        out["shortfall"] = r2(max(0.0, loan - max_loan))
        out["failed_constraints"] = [k for k, v in constraints.items() if loan > v + 0.005]
    return out


def underwrite(a: dict) -> dict:
    """NOI then loan sizing in one call. ``a`` mixes :func:`noi` and :func:`size_loan` keyword arguments; give
    ``noi`` directly to skip the income build, or ``rent_roll`` (+ ``as_of``) to take gross potential rent from
    :func:`decision_ladder.commercial.rentroll.analyze`."""
    a = dict(a)
    noi_keys = ("gross_potential_rent", "other_income", "vacancy_pct", "expense_ratio_pct", "expenses",
                "management_pct", "reserves_per_unit", "units")
    out: dict = {}
    if "rent_roll" in a:
        from .rentroll import analyze
        rr = analyze(a.pop("rent_roll"), a.pop("as_of"))
        a["gross_potential_rent"] = rr["gross_potential_rent"]
        out["rent_roll"] = {k: rr[k] for k in ("gross_potential_rent", "physical_occupancy_pct", "walt_years_by_rent", "flags")}
    if "noi" in a:
        inc = {"noi": r2(positive("noi", a.pop("noi")))}
        for k in noi_keys:
            a.pop(k, None)
    else:
        inc = noi(**{k: a.pop(k) for k in noi_keys if k in a})
    out.update({"income": inc, "sizing": size_loan(noi=inc["noi"], **a), "assumptions": ASSUMPTIONS,
                "engine": "commercial.underwriting"})
    return out

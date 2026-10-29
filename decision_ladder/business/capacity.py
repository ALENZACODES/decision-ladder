"""Business borrower capacity: normalized EBITDA, cash available for debt service, business and global DSCR, and
the largest new loan that keeps both at or above a target."""
from __future__ import annotations

from ..engines import payments
from . import cashflow as cf


def normalized_ebitda(net_income: float, interest_expense: float = 0.0, income_taxes: float = 0.0,
                      depreciation_amortization: float = 0.0, add_backs: list[dict] | None = None,
                      owner_compensation_paid: float | None = None, market_compensation: float | None = None) -> dict:
    """EBITDA from the income statement plus documented add-backs (one-time items, as {"label", "amount"};
    negative amounts are deductions) and an owner-compensation normalization: pay above a market salary for the
    role is added back, pay below it is deducted."""
    ebitda = net_income + interest_expense + income_taxes + depreciation_amortization
    items = [{"label": str(a.get("label", "add-back")), "amount": float(a["amount"])} for a in (add_backs or [])]
    if owner_compensation_paid is not None and market_compensation is not None:
        adj = owner_compensation_paid - market_compensation
        if adj:
            items.append({"label": "owner compensation to market", "amount": adj})
    adjusted = ebitda + sum(i["amount"] for i in items)
    return {"ebitda": round(ebitda, 2), "adjustments": items, "adjusted_ebitda": round(adjusted, 2)}


def loan_annual_debt_service(amount: float, annual_rate_pct: float, amort_years: float) -> float:
    """Annual P&I on a monthly-pay business loan quoted nominal monthly."""
    return payments.payment(amount, annual_rate_pct, amort_years, "monthly") * 12


def max_loan_for_debt_service(annual_debt_service: float, annual_rate_pct: float, amort_years: float) -> float:
    if annual_debt_service <= 0:
        return 0.0
    return cf.annuity_pv(annual_debt_service / 12, annual_rate_pct / 1200, round(amort_years * 12))


def dscr(net_income: float, existing_business_debt_service: float, interest_expense: float = 0.0,
         income_taxes: float = 0.0, depreciation_amortization: float = 0.0, add_backs: list[dict] | None = None,
         owner_compensation_paid: float | None = None, market_compensation: float | None = None,
         unfunded_capex: float = 0.0, cash_taxes: float | None = None, distributions: float = 0.0,
         proposed_loan: dict | None = None, target_dscr: float = 1.25, new_loan_rate_pct: float | None = None,
         new_loan_amort_years: float | None = None, owner: dict | None = None,
         target_global_dscr: float | None = None) -> dict:
    """Business DSCR and, with ``owner``, global DSCR.

    Cash available for debt service (CADS) = adjusted EBITDA - unfunded capex - cash taxes - distributions
    (owner draws/dividends beyond the market salary already in expenses). ``cash_taxes`` defaults to the income
    tax expense. ``proposed_loan`` = {amount, annual_rate_pct, amort_years}.

    ``owner`` = {personal_income, personal_taxes, living_expenses, personal_debt_service}, all annual. Personal
    income should include salary and distributions from this business; global cash flow is business CADS plus
    owner income less personal taxes and living costs, over business plus personal debt service.
    """
    if existing_business_debt_service < 0 or target_dscr <= 0:
        raise ValueError("debt service must be >= 0 and target DSCR > 0")
    e = normalized_ebitda(net_income, interest_expense, income_taxes, depreciation_amortization, add_backs,
                          owner_compensation_paid, market_compensation)
    taxes = income_taxes if cash_taxes is None else cash_taxes
    cads = e["adjusted_ebitda"] - unfunded_capex - taxes - distributions
    new_ds = 0.0
    if proposed_loan:
        new_ds = loan_annual_debt_service(float(proposed_loan["amount"]), float(proposed_loan["annual_rate_pct"]),
                                          float(proposed_loan["amort_years"]))
    total_ds = existing_business_debt_service + new_ds

    def ratio(cash: float, ds: float) -> float | None:
        return round(cash / ds, 4) if ds > 0 else None

    out = {**e, "cash_taxes": round(taxes, 2), "unfunded_capex": unfunded_capex, "distributions": distributions,
           "cads": round(cads, 2), "existing_debt_service": round(existing_business_debt_service, 2),
           "proposed_debt_service": round(new_ds, 2), "total_debt_service": round(total_ds, 2),
           "dscr_existing": ratio(cads, existing_business_debt_service), "dscr_pro_forma": ratio(cads, total_ds),
           "target_dscr": target_dscr}
    out["passes_target"] = None if total_ds == 0 else cads / total_ds >= target_dscr

    rate = new_loan_rate_pct if new_loan_rate_pct is not None else (proposed_loan or {}).get("annual_rate_pct")
    amort = new_loan_amort_years if new_loan_amort_years is not None else (proposed_loan or {}).get("amort_years")
    room = {"business": max(0.0, cads / target_dscr - existing_business_debt_service)}

    if owner:
        o = {k: float(owner.get(k, 0.0)) for k in ("personal_income", "personal_taxes", "living_expenses",
                                                     "personal_debt_service")}
        g_cash = cads + o["personal_income"] - o["personal_taxes"] - o["living_expenses"]
        g_ds = total_ds + o["personal_debt_service"]
        g_target = target_global_dscr or target_dscr
        out["global"] = {"cash_flow": round(g_cash, 2), "debt_service": round(g_ds, 2),
                         "dscr_pro_forma": ratio(g_cash, g_ds), "target": g_target,
                         "passes_target": None if g_ds == 0 else g_cash / g_ds >= g_target}
        room["global"] = max(0.0, g_cash / g_target - existing_business_debt_service - o["personal_debt_service"])

    if rate is not None and amort:
        sizes = {k: round(max_loan_for_debt_service(v, float(rate), float(amort)), 2) for k, v in room.items()}
        binding = min(sizes, key=sizes.get)
        out["max_new_loan"] = {"amount": sizes[binding], "binding_constraint": binding, "by_constraint": sizes,
                               "annual_debt_service_room": {k: round(v, 2) for k, v in room.items()},
                               "rate_pct": rate, "amort_years": amort}
    out["engine"] = "business.capacity.dscr"
    out["source"] = "borrower financial statements as entered; no external data"
    out["assumptions"] = {"cads": "adjusted EBITDA - unfunded capex - cash taxes - distributions",
                          "loan_payments": "new loan sized at monthly payments, rate nominal monthly"}
    return out

"""Unsecured business credit: amortizing term loan, revolving line of credit, merchant cash advance.

Every product is reduced to its actual cash flows from the borrower's side (cash in at funding, payments out
on their dates) and costed with the IRR solver, so fees and timing are in the APR rather than added on.
"""
from __future__ import annotations

import math

from . import cashflow as cf
from . import usury
from .params import assumptions


def amortize(loan: float, periodic_rate: float, n: int, payment: float | None = None) -> list[dict]:
    """Period-by-period schedule: interest, principal and closing balance (last payment absorbs rounding)."""
    pmt = cf.annuity_payment(loan, periodic_rate, n) if payment is None else payment
    bal, rows = loan, []
    for k in range(1, n + 1):
        interest = bal * periodic_rate
        principal = bal if k == n else min(bal, pmt - interest)
        bal -= principal
        rows.append({"period": k, "payment": interest + principal, "interest": interest, "principal": principal,
                     "balance": max(bal, 0.0)})
    return rows


def _usury(apr_pct: float, credit: float, a: dict) -> dict:
    return usury.check(apr_pct, credit, bool(a.get("borrower_is_natural_person", False)),
                       bool(a.get("business_purpose", True)))


def term_loan(principal: float, annual_rate_pct: float, years: float, payments_per_year: int = 12,
              upfront_fees: float = 0.0, financed_fees: float = 0.0, borrower_is_natural_person: bool = False,
              business_purpose: bool = True) -> dict:
    """Level-payment unsecured term loan. ``upfront_fees`` come off the cash advanced; ``financed_fees`` are added
    to the loan balance. APR is from the borrower's net proceeds versus the payments."""
    if principal <= 0 or years <= 0 or annual_rate_pct < 0:
        raise ValueError("principal and years must be positive, rate >= 0")
    if not 0 <= upfront_fees < principal or financed_fees < 0:
        raise ValueError("fees must be >= 0 and upfront fees below the principal")
    ppy = int(payments_per_year)
    n = round(years * ppy)
    loan = principal + financed_fees
    i = annual_rate_pct / 100 / ppy
    rows = amortize(loan, i, n)
    net = principal - upfront_fees
    flows = [net] + [-r["payment"] for r in rows]
    rates = cf.rate_summary(cf.irr(flows), ppy)
    total_paid = sum(r["payment"] for r in rows)
    return {"product": "unsecured term loan", "loan_amount": round(loan, 2), "net_proceeds": round(net, 2),
            "payment": round(rows[0]["payment"], 2), "payments": n, "payments_per_year": ppy,
            "total_interest": round(sum(r["interest"] for r in rows), 2), "total_paid": round(total_paid, 2),
            "total_cost_of_credit": round(total_paid - net, 2), "contract_rate_pct": annual_rate_pct,
            **{k: rates[k] for k in ("apr_pct", "ear_pct")},
            "criminal_rate": _usury(rates["apr_pct"], net, {"borrower_is_natural_person": borrower_is_natural_person,
                                                           "business_purpose": business_purpose}),
            "engine": "business.unsecured.term_loan",
            "assumptions": assumptions("apr_method", "csbfp_rate_compounding")}


def line_of_credit(limit: float, average_drawn: float, annual_rate_pct: float, standby_fee_pct: float = 0.0,
                   annual_fee: float = 0.0, setup_fee: float = 0.0, expected_years: float = 1.0,
                   borrower_is_natural_person: bool = False, business_purpose: bool = True) -> dict:
    """Annual cost of a revolving line: interest on the average drawn balance (monthly compounding), standby fee on
    the undrawn limit, the annual fee, and any setup fee spread evenly over the expected life of the line."""
    if limit <= 0 or not 0 < average_drawn <= limit or expected_years <= 0:
        raise ValueError("need limit > 0, 0 < average drawn <= limit, expected years > 0")
    interest = average_drawn * ((1 + annual_rate_pct / 1200) ** 12 - 1)
    standby = (limit - average_drawn) * standby_fee_pct / 100
    setup = setup_fee / expected_years
    total = interest + standby + annual_fee + setup
    ear = total / average_drawn
    apr = cf.apr_from_ear(ear, 12) * 100
    return {"product": "business line of credit", "limit": limit, "average_drawn": average_drawn,
            "annual_cost": {"interest": round(interest, 2), "standby_fee": round(standby, 2),
                            "annual_fee": round(annual_fee, 2), "setup_fee_amortized": round(setup, 2),
                            "total": round(total, 2)},
            "effective_annual_cost_on_drawn_pct": round(ear * 100, 4), "apr_pct": round(apr, 4),
            "utilization_pct": round(average_drawn / limit * 100, 2),
            "criminal_rate": _usury(apr, average_drawn, {"borrower_is_natural_person": borrower_is_natural_person,
                                                        "business_purpose": business_purpose}),
            "note": "Revolving balances vary; cost is annualized on the average drawn balance, so low utilization "
                    "with standby or annual fees raises the effective rate.",
            "engine": "business.unsecured.line_of_credit", "assumptions": assumptions("apr_method")}


def _remit_day(k: int, days_per_week: int) -> int:
    """Calendar day of the k-th remittance (k >= 1) when remittances run ``days_per_week`` days a week."""
    week, dow = divmod(k - 1, days_per_week)
    return 7 * week + dow + 1


def mca_flows(advance: float, factor_rate: float, daily_remittance: float, fees: float = 0.0,
              days_per_week: int = 5) -> list[tuple[float, float]]:
    """Dated borrower cash flows of a merchant cash advance: net funding at day 0, then remittances until the
    purchased amount (advance x factor) is repaid; the final remittance is the remainder."""
    payback = advance * factor_rate
    n = math.ceil(payback / daily_remittance - 1e-9)
    flows = [(0.0, advance - fees)]
    for k in range(1, n + 1):
        amt = daily_remittance if k < n else payback - daily_remittance * (n - 1)
        flows.append((float(_remit_day(k, days_per_week)), -amt))
    return flows


def merchant_cash_advance(advance: float, factor_rate: float, holdback_pct: float | None = None,
                          expected_daily_sales: float | None = None, expected_remittance_days: int | None = None,
                          fees: float = 0.0, days_per_week: int = 5, sensitivity_days: list[int] | None = None,
                          borrower_is_natural_person: bool = False, business_purpose: bool = True) -> dict:
    """Implied cost of an MCA. Give either holdback % with expected daily card sales, or the expected number of
    remittance days. A business whose sales come in faster than expected pays the same dollars sooner, so the
    APR rises: ``sensitivity_days`` shows that."""
    if advance <= 0 or factor_rate <= 1 or not 0 <= fees < advance:
        raise ValueError("need advance > 0, factor rate > 1 and fees below the advance")
    if days_per_week not in (5, 6, 7):
        raise ValueError("days_per_week must be 5, 6 or 7")
    payback = advance * factor_rate
    if expected_remittance_days:
        daily = payback / int(expected_remittance_days)
    elif holdback_pct and expected_daily_sales:
        daily = expected_daily_sales * holdback_pct / 100
    else:
        raise ValueError("give expected_remittance_days, or holdback_pct with expected_daily_sales")

    def cost(daily_amt: float) -> dict:
        flows = mca_flows(advance, factor_rate, daily_amt, fees, days_per_week)
        ear = cf.xirr(flows)
        term = flows[-1][0]
        return {"remittances": len(flows) - 1, "calendar_days": int(term), "daily_remittance": round(daily_amt, 2),
                "ear_pct": round(ear * 100, 4), "apr_pct": round(cf.apr_from_ear(ear, cf.DAYS_PER_YEAR) * 100, 4),
                "simple_annualized_pct": round((payback - advance + fees) / (advance - fees) * cf.DAYS_PER_YEAR / term * 100, 4)}

    base = cost(daily)
    out = {"product": "merchant cash advance", "advance": advance, "fees": fees, "net_funded": round(advance - fees, 2),
           "factor_rate": factor_rate, "purchased_amount": round(payback, 2),
           "cost_of_capital": round(payback - advance + fees, 2), **base,
           "criminal_rate": _usury(base["apr_pct"], advance - fees,
                                   {"borrower_is_natural_person": borrower_is_natural_person,
                                    "business_purpose": business_purpose}),
           "engine": "business.unsecured.merchant_cash_advance",
           "assumptions": assumptions("apr_method", "credit_advanced_net_of_fees", "mca_characterization")}
    if holdback_pct and expected_daily_sales:
        out["holdback_pct"] = holdback_pct
    if sensitivity_days:
        out["sensitivity"] = [{"remittance_days": d, **{k: v for k, v in cost(payback / d).items()
                                                         if k in ("calendar_days", "apr_pct", "ear_pct")}}
                              for d in sorted({int(d) for d in sensitivity_days if int(d) > 0})]
    return out

"""Bridge and private first / second mortgages: fees, interest-only payments, net advance and true cost.

The cost of a private loan is not its coupon: lender and broker fees come off the advance, interest may be
prepaid out of it, there can be an exit (renewal / discharge) fee, and many private lenders charge a minimum
number of months of interest. The effective cost is the IRR of the borrower's actual cash flows: net money in at
closing, monthly interest out, principal plus exit fee out at the end.

Criminal interest rate screen (Criminal Code s.347 as amended Jan 1, 2025; checked 2026-10-29 against
Stewart McKelvey's summary): 35% APR in general; for loans to a borrower that is not a natural person for
business purposes, 48% APR when the credit is over $10,000 up to $500,000 and no limit above $500,000.
"Interest" there includes all charges. The screen below compares the IRR-based APR (monthly IRR x 12) to the
limit; it is an indicative flag, not legal advice.
"""
from __future__ import annotations

from .common import irr, pct, positive, r2, ratio

SOURCES = {"criminal_rate": "https://stewartmckelvey.com/thought-leadership/canadas-new-criminal-rate-of-interest-takes-effect/",
           "checked": "2026-10-29"}
CRIMINAL_APR_GENERAL, CRIMINAL_APR_COMMERCIAL_MID = 35.0, 48.0
COMMERCIAL_LOW, COMMERCIAL_HIGH = 10_000.0, 500_000.0


def criminal_rate_limit(loan: float, natural_person: bool, business_purpose: bool) -> float | None:
    """APR limit in percent, or None when no limit applies."""
    if natural_person or not business_purpose or loan <= COMMERCIAL_LOW:
        return CRIMINAL_APR_GENERAL
    return CRIMINAL_APR_COMMERCIAL_MID if loan <= COMMERCIAL_HIGH else None


def _flows(loan: float, i: float, exit_month: int, prepaid: int, min_months: int, upfront: float, exit_fee: float) -> list[float]:
    """Borrower cash flows by month for an exit at ``exit_month`` (interest paid monthly in arrears)."""
    flows = [loan - upfront] + [0.0] * exit_month
    for m in range(1, exit_month + 1):
        if m > prepaid:
            flows[m] -= loan * i
    owed_months = max(min_months, exit_month)
    short = max(0, owed_months - max(exit_month, prepaid))   # minimum-interest top-up charged at payout
    flows[exit_month] -= loan + exit_fee + short * loan * i
    return flows


def _annualize(m: float) -> tuple[float, float]:
    return (1 + m) ** 12 - 1, m * 12


def cost(*, loan: float, rate_pct: float, term_months: int, lender_fee_pct: float = 0.0, broker_fee_pct: float = 0.0,
         other_costs: float = 0.0, prepaid_interest_months: int = 0, exit_fee_pct: float = 0.0,
         min_interest_months: int = 0, compounding: str = "monthly", value: float | None = None,
         prior_balance: float = 0.0, natural_person: bool = False, business_purpose: bool = True) -> dict:
    """Net advance, payments and effective annual cost of an interest-only private loan.

    ``other_costs``: legal, appraisal and admin the borrower pays at closing, dollars. ``prior_balance``: existing
    mortgages ranking ahead (for a second). Rates and fees in percent.
    """
    loan = positive("loan", loan)
    term = int(term_months)
    if term < 1:
        raise ValueError("term_months must be at least 1")
    prepaid = max(0, min(int(prepaid_interest_months), term))
    min_m = max(0, int(min_interest_months))
    if compounding == "monthly":
        i = positive("rate_pct", rate_pct) / 100 / 12
    elif compounding == "semi":
        i = (1 + positive("rate_pct", rate_pct) / 200) ** (1 / 6) - 1
    else:
        raise ValueError("compounding must be 'monthly' or 'semi'")
    lender_fee = loan * ratio("lender_fee_pct", lender_fee_pct) / 100
    broker_fee = loan * ratio("broker_fee_pct", broker_fee_pct) / 100
    other = positive("other_costs", other_costs, allow_zero=True)
    prepaid_amt = loan * i * prepaid
    exit_fee = loan * ratio("exit_fee_pct", exit_fee_pct) / 100
    upfront = lender_fee + broker_fee + other + prepaid_amt
    if upfront >= loan:
        raise ValueError("fees and prepaid interest exceed the loan")

    flows = _flows(loan, i, term, prepaid, min_m, upfront, exit_fee)
    eff, apr = _annualize(irr(flows))
    lender_flows = _flows(loan, i, term, prepaid, min_m, lender_fee + prepaid_amt, exit_fee)
    lender_eff, _ = _annualize(irr(lender_flows))
    interest_total = loan * i * max(term, min_m)
    limit = criminal_rate_limit(loan, natural_person, business_purpose)

    exits = []
    for e in sorted({m for m in (1, 3, 6, 9, 12, min_m, term) if 1 <= m <= term}):
        ee, ea = _annualize(irr(_flows(loan, i, e, prepaid, min_m, upfront, exit_fee)))
        exits.append({"exit_month": e, "effective_annual_cost_pct": pct(ee), "apr_pct": pct(ea)})

    out = {
        "loan": r2(loan), "rate_pct": rate_pct, "compounding": compounding, "term_months": term,
        "monthly_interest": r2(loan * i),
        "fees": {"lender": r2(lender_fee), "broker": r2(broker_fee), "other": r2(other), "exit": r2(exit_fee),
                 "prepaid_interest": r2(prepaid_amt)},
        "net_advance": r2(loan - upfront),
        "total_interest": r2(interest_total),
        "total_cost_of_borrowing": r2(interest_total + lender_fee + broker_fee + other + exit_fee),
        "effective_annual_cost_pct": pct(eff, 4), "apr_pct": pct(apr, 4),
        "coupon_effective_annual_pct": pct((1 + i) ** 12 - 1),
        "lender_yield_pct": pct(lender_eff),
        "early_exit": exits,
        "criminal_rate_limit_apr_pct": limit,
        "criminal_rate_flag": limit is not None and apr * 100 > limit,
        "early_exits_over_limit": [] if limit is None else [x["exit_month"] for x in exits if x["apr_pct"] > limit],
    }
    if value:
        v = positive("value", value)
        prior = positive("prior_balance", prior_balance, allow_zero=True)
        out["position"] = "second" if prior else "first"
        out["ltv_pct"] = pct(loan / v)
        out["combined_ltv_pct"] = pct((loan + prior) / v)
    out["cash_flows"] = [r2(f) for f in flows]
    out["sources"] = SOURCES
    out["assumptions"] = [
        "interest-only, paid monthly in arrears; principal and exit fee repaid at the end",
        "prepaid interest covers the first months and is not refunded on early exit",
        "minimum-interest shortfall is charged at payout",
        "effective cost = (1 + monthly IRR)^12 - 1; APR = monthly IRR x 12; lender yield excludes the broker fee and "
        "other borrower costs",
        "criminal-rate flag is an indicative screen on the full term (early exits listed separately), not legal advice",
    ]
    out["engine"] = "commercial.bridge"
    return out

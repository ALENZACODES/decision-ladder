"""Renewal shock and switch analysis.

At renewal the balance is re-amortized over the remaining amortization at the new rate. The *payment
shock* is the change in the regular payment. A borrower who switches to another lender at renewal on an
uninsured mortgage generally must pass the B-20 stress test again (OSFI removed this requirement for
straight switches of uninsured mortgages at renewal effective Nov 21, 2024); insured mortgages switching
at renewal do not need to requalify. This module reports both views and labels the rule it used.
"""
from __future__ import annotations

from .payments import balance_after, payment
from .qualify import qualifying_rate

SWITCH_RULE = ("Since Nov 21, 2024 OSFI does not require a straight switch of an uninsured mortgage at renewal "
               "to be re-stress-tested if the amount and amortization do not increase. Lender policy may still apply.")


def renewal_shock(*, original_principal: float, original_rate: float, original_amort_years: float,
                  months_elapsed: int, renewal_rate: float) -> dict:
    """Payment before and after renewal, with the balance carried from the original schedule."""
    if months_elapsed <= 0 or months_elapsed >= original_amort_years * 12:
        raise ValueError("months_elapsed must be within the amortization")
    old_pmt = payment(original_principal, original_rate, original_amort_years)
    bal = balance_after(original_principal, original_rate, original_amort_years, months_elapsed)
    remaining_years = original_amort_years - months_elapsed / 12
    new_pmt = payment(bal, renewal_rate, remaining_years)
    return {
        "balance_at_renewal": round(bal, 2), "remaining_amort_years": round(remaining_years, 2),
        "payment_before": round(old_pmt, 2), "payment_after": round(new_pmt, 2),
        "monthly_change": round(new_pmt - old_pmt, 2),
        "pct_change": round((new_pmt / old_pmt - 1) * 100, 2),
        "annual_change": round((new_pmt - old_pmt) * 12, 2),
    }


def offer_comparison(*, balance: float, remaining_amort_years: float, term_years: float,
                     offers: list[dict]) -> dict:
    """Compare renewal offers over the term: payment, interest paid, balance at term end, net of fees.

    Each offer: {"label": str, "rate": float, "fees": float (optional), "cashback": float (optional)}.
    """
    if not offers:
        raise ValueError("at least one offer is required")
    months = int(round(term_years * 12))
    rows = []
    for o in offers:
        rate = float(o["rate"])
        pmt = payment(balance, rate, remaining_amort_years)
        end_bal = balance_after(balance, rate, remaining_amort_years, months)
        interest = pmt * months - (balance - end_bal)
        net = interest + float(o.get("fees", 0.0)) - float(o.get("cashback", 0.0))
        rows.append({"label": o.get("label", f"{rate}%"), "rate": rate, "payment": round(pmt, 2),
                     "interest_over_term": round(interest, 2), "balance_at_term_end": round(end_bal, 2),
                     "fees": float(o.get("fees", 0.0)), "cashback": float(o.get("cashback", 0.0)),
                     "net_cost_over_term": round(net, 2)})
    rows.sort(key=lambda r: r["net_cost_over_term"])
    best = rows[0]
    for r in rows:
        r["extra_cost_vs_best"] = round(r["net_cost_over_term"] - best["net_cost_over_term"], 2)
    return {"term_years": term_years, "offers": rows, "lowest_net_cost": best["label"]}


def switch_check(*, balance: float, remaining_amort_years: float, new_rate: float, annual_income: float,
                 property_tax_annual: float = 0.0, heat_annual: float = 1800.0, condo_fees_monthly: float = 0.0,
                 other_debt_monthly: float = 0.0, insured: bool = False, increases_amount_or_amort: bool = False) -> dict:
    """Would this borrower pass the stress test at another lender? And do they need to?"""
    qr = qualifying_rate(new_rate)
    stressed = payment(balance, qr, remaining_amort_years)
    inc_m = annual_income / 12
    housing = stressed + property_tax_annual / 12 + heat_annual / 12 + 0.5 * condo_fees_monthly
    gds, tds = housing / inc_m * 100, (housing + other_debt_monthly) / inc_m * 100
    passes = gds <= 39 and tds <= 44
    needs = increases_amount_or_amort and not insured
    return {"qualifying_rate": qr, "stressed_payment": round(stressed, 2), "gds": round(gds, 2), "tds": round(tds, 2),
            "would_pass_stress_test": passes, "stress_test_required": needs,
            "can_switch": passes or not needs, "rule": SWITCH_RULE if not insured else
            "Insured mortgages switching at renewal do not need to requalify under the stress test."}


def renewal_priority(*, months_to_maturity: int, pct_change: float, balance: float, ltv: float | None = None) -> dict:
    """0-100 priority score for a broker's renewal queue: sooner, bigger shock, bigger balance first."""
    urgency = max(0.0, min(1.0, (12 - months_to_maturity) / 12)) if months_to_maturity >= 0 else 1.0
    shock = max(0.0, min(1.0, pct_change / 30))
    size = max(0.0, min(1.0, balance / 1_000_000))
    risk = 0.0 if ltv is None else max(0.0, min(1.0, (ltv - 65) / 30))
    score = round(100 * (0.40 * urgency + 0.35 * shock + 0.15 * size + 0.10 * risk), 1)
    tier = "call this week" if score >= 60 else "call this month" if score >= 35 else "watch"
    return {"score": score, "tier": tier,
            "components": {"urgency": round(urgency, 3), "shock": round(shock, 3), "size": round(size, 3), "ltv_risk": round(risk, 3)}}

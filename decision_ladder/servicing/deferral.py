"""Payment deferral and arrears.

**Deferral** (a skip-a-payment or hardship deferral agreed with the lender): no payment is made on the
deferred dates, but interest keeps accruing at the contract rate and is added to the balance (capitalized).
Two ways back are compared against the schedule without a deferral:

* *keep the payment*: the regular payment resumes unchanged, so the amortization runs longer;
* *re-amortize*: the payment is raised so the mortgage still pays off on the original payoff date.

**Arrears** (payments simply missed): each missed payment is owed in full, and the lender charges interest
on the overdue amount at the mortgage rate. The amount to cure on a given payment date is
``sum(payment x (1 + i) ** periods_overdue)`` plus any NSF/administration fees. Whether a lender
compounds arrears interest at the periodic mortgage rate (as here) or charges simple interest is a
contract term.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from . import frequency as F
from .schedule import Events, LoanSpec, build


def _first_index_on_or_after(spec: LoanSpec, start: date) -> int:
    k = 0
    while F.payment_date(spec.first_payment, spec.frequency, k) < start:
        k += 1
    return k


def defer_payments(spec: LoanSpec, start: date, n_payments: int, rows: bool = False) -> dict:
    """Effect of skipping ``n_payments`` regular payments from ``start``."""
    if n_payments <= 0:
        raise ValueError("number of deferred payments must be positive")
    spec = replace(spec, term_months=None)
    k0 = _first_index_on_or_after(spec, start)
    skipped = [F.payment_date(spec.first_payment, spec.frequency, k0 + j) for j in range(n_payments)]
    resume = F.payment_date(spec.first_payment, spec.frequency, k0 + n_payments)
    base = build(spec)
    if not base.rows or skipped[0] > base.rows[-1].date:
        raise ValueError("deferral starts after the mortgage is paid off")
    keep = build(spec, Events(skips=skipped))
    before = keep.balance_on(F.payment_date(spec.first_payment, spec.frequency, k0 - 1))
    after = keep.balance_on(skipped[-1])
    deferred_interest = sum(r.interest for r in keep.rows if "skipped" in r.flags)

    # re-amortize: level payment from the resume date that ends on the original payoff date
    remaining = sum(1 for r in base.rows if r.date >= resume)
    i = F.periodic_rate(spec.rate_on(resume), spec.freq.per_year, spec.compounding)
    new_pmt = F.annuity(after, i, remaining) if remaining > 0 else after
    reamort = build(spec, Events(skips=skipped, payment_changes=[(resume, new_pmt)]))

    b, k, r = base.summary(), keep.summary(), reamort.summary()
    out = {
        "deferred_dates": [d.isoformat() for d in skipped], "resume_date": resume.isoformat(),
        "balance_before_deferral": round(before, 2), "balance_after_deferral": round(after, 2),
        "capitalized_interest": round(deferred_interest, 2),
        "payments_not_made": round(base.rows[0].payment * n_payments, 2),
        "baseline": {k_: b[k_] for k_ in ("initial_payment", "payoff_date", "total_interest", "payments_made")},
        "keep_payment": {"payment": k["final_regular_payment"], "payoff_date": k["payoff_date"],
                         "total_interest": k["total_interest"],
                         "extra_interest": round(k["total_interest"] - b["total_interest"], 2),
                         "extra_payments": k["payments_made"] - n_payments - b["payments_made"]},
        "reamortize": {"payment": round(new_pmt, 2), "payment_increase": round(new_pmt - b["initial_payment"], 2),
                       "payoff_date": r["payoff_date"], "total_interest": r["total_interest"],
                       "extra_interest": round(r["total_interest"] - b["total_interest"], 2)},
        "method": ("Interest accrues on skipped dates at the contract rate and is capitalized; 'keep_payment' resumes "
                   "the old payment, 'reamortize' resets it to finish on the original payoff date."),
    }
    if rows:
        out["schedule_keep_payment"] = keep.as_dict(rows=True)
    return out


def arrears(payment: float, annual_rate: float, missed: int, frequency: str = "monthly", rate_type: str = "fixed",
            fees_per_missed: float = 0.0) -> dict:
    """Amount needed to bring a mortgage current after ``missed`` consecutive missed payments."""
    if payment <= 0 or missed <= 0:
        raise ValueError("payment and missed must be positive")
    f = F.get(frequency)
    i = F.periodic_rate(annual_rate, f.per_year, F.compounding_for(rate_type))
    owed = [payment * (1 + i) ** (missed - j) for j in range(1, missed + 1)]
    principal_due = payment * missed
    interest = sum(owed) - principal_due
    fees = fees_per_missed * missed
    return {"missed_payments": missed, "frequency": f.key, "payments_due": round(principal_due, 2),
            "interest_on_arrears": round(interest, 2), "fees": round(fees, 2),
            "amount_to_cure": round(sum(owed) + fees, 2),
            "method": "each missed payment accrues interest at the periodic mortgage rate until the cure date "
                      "(the date of the latest missed payment)"}

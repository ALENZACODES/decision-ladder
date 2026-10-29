"""Renewal disclosure timing.

* Federal (banks): Financial Consumer Protection Framework Regulations s. 45: a renewal statement at least 21 days
  before the renewal date, containing the s. 40/41 cost information, a statement that nothing increasing the cost
  of borrowing will change before renewal, and a statement that the borrower's rights continue, and the renewal
  does not take effect, until the later of the renewal date and 21 days after the borrower receives it.
  "At least 21 days" is counted under Interpretation Act s. 27(1): both days excluded.
* Ontario: O. Reg. 191/08 s. 14 (where the brokerage is the lender): the same 21-day statement and contents
  (s. 14(2)-(3)), and at least 21 days' notice before the term ends if it will not renew (s. 14(4)). Counted
  under Legislation Act, 2006 s. 89(3): the last day is counted.
No Alberta renewal-timing rule was verified, so none is applied.
"""
from __future__ import annotations

from datetime import timedelta

from .calendar import _d, at_least_days_before
from .cost_of_borrowing import cost_of_borrowing
from .sources import cite, envelope

DAYS = 21
CONTENT = {
    "includes_cost_information": "cost of borrowing information for the renewal term (s. 40/41 federal; s. 8/9 Ontario)",
    "includes_no_increase_statement": "statement that no change increasing the cost of borrowing will be made before "
                                      "renewal",
    "includes_rights_statement": "statement that rights continue, and renewal does not take effect, until the later of "
                                 "the renewal date and 21 days after receipt",
}


def check(a: dict) -> dict:
    maturity = _d(a["maturity_date"])
    regime = a.get("regime", "federal_bank")
    if regime not in ("federal_bank", "ontario_lender"):
        raise ValueError("regime must be federal_bank or ontario_lender")
    convention = "federal" if regime == "federal_bank" else "ontario"
    out: dict = {"regime": regime, "maturity_date": maturity.isoformat()}
    cites = ([cite("FCPF_REGS", "s. 45"), cite("INTERPRETATION_ACT", "s. 27(1)")] if regime == "federal_bank"
             else [cite("ON_191_08", "s. 14"), cite("ON_LEGISLATION_ACT", "s. 89(3)")])
    if regime == "ontario_lender" and not a.get("brokerage_is_lender", True):
        out.update(applies=False, finding="O. Reg. 191/08 s. 14 applies where the brokerage is the lender; the "
                                          "renewing lender's own regime governs")
        return envelope(out, "disclosure.renewal", cites)

    if a.get("will_not_renew"):
        if regime != "ontario_lender":
            raise ValueError("non-renewal notice timing is implemented for ontario_lender only")
        if not a.get("notice_date"):
            raise ValueError("notice_date is required when will_not_renew is true")
        t = at_least_days_before(a["notice_date"], maturity, DAYS, convention)
        out.update(applies=True, kind="non-renewal notice (s. 14(4))", ok=t["ok"], timing=t,
                   finding=("notice in time" if t["ok"] else
                            f"notice {t['short_by_days']} day(s) late; latest compliant date {t['latest_compliant_date']}"))
        return envelope(out, "disclosure.renewal", cites)

    t = at_least_days_before(a["statement_date"], maturity, DAYS, convention)
    received = _d(a.get("received_date") or a["statement_date"])
    effective = max(maturity, received + timedelta(days=DAYS))
    missing = [desc for k, desc in CONTENT.items() if not a.get(k)]
    out.update(applies=True, kind="renewal statement", ok=t["ok"] and not missing, timing=t,
               received_date=received.isoformat(), renewal_effective_no_earlier_than=effective.isoformat(),
               rights_extended=effective > maturity, missing_content=missing)
    if t["ok"]:
        out["finding"] = f"statement {t['days_counted']} counted days before the renewal date"
    else:
        out["finding"] = (f"statement {t['short_by_days']} day(s) late; latest compliant date "
                          f"{t['latest_compliant_date']}; renewal cannot take effect before {effective.isoformat()}")
    if a.get("renewal_terms"):
        rt = a["renewal_terms"]
        cob = cost_of_borrowing(rt["balance"], rt["annual_rate"], rt["amort_years"], int(rt["term_months"]),
                                rt.get("compounding", "semi"), rt.get("frequency", "monthly"), rt.get("charges"),
                                rate_type=rt.get("rate_type", "fixed"))
        out["renewal_cost"] = {k: cob[k] for k in ("payment", "total_payments", "interest_over_term",
                                                   "cost_of_borrowing", "apr_pct", "balance_at_maturity")}
        cites += cob["citations"]
    return envelope(out, "disclosure.renewal", cites)

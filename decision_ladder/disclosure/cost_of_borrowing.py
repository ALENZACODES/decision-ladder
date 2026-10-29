"""Cost of borrowing, APR and the initial disclosure statement under Ontario O. Reg. 191/08.

APR (s. 3(1)):  APR = 100 * C / (T * P)
    C  cost of borrowing over the term (s. 5: interest plus the included non-interest charges)
    T  term in years (s. 3(2)(c): a month is 1/12, a week 1/52 of a year)
    P  average principal outstanding at the end of each period, before subtracting the payment due then.
       Payments go to accrued cost of borrowing first (s. 3(2)(b)), so within a period the principal is the
       opening balance; P is therefore the mean of the opening balances of the term's payment periods.

s. 4(1): where interest is the only cost of borrowing, the APR is the annual interest rate.
s. 4(2): where the rate is disclosed under Interest Act s. 6 (e.g. compounded half-yearly), the APR is calculated
         consistently with that section. Here that is implemented by restating the s. 3(1) figure, which is a
         nominal rate per payment period, on the compounding basis of the quoted rate. That restatement is this
         desk's interpretation of "consistent with", and it reduces exactly to s. 4(1) when there are no fees.

The federal Financial Consumer Protection Framework Regulations s. 47(1) use the same formula; no equivalent of
Ontario s. 4(1) was found in s. 47, so the federal comparison is the raw formula figure (optionally rounded to the
nearest 1/8 %, s. 47(2)(a)). For a semi-annually compounded mortgage the two differ even with no fees.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..engines import payments
from .calendar import _d, business_days_between, latest_date_with_business_days_before
from .sources import cite, envelope

FREQ = {"monthly": 12, "biweekly": 26, "weekly": 52}
COMP_PER_YEAR = {"semi": 2, "monthly": 12}

# type -> (included in cost of borrowing?, citation source, section, description)
CHARGE_TYPES: dict[str, tuple[bool, str, str, str]] = {
    "admin": (True, "ON_191_08", "s. 5(1) para. 1", "administrative charges"),
    "lender_lawyer": (True, "ON_191_08", "s. 5(1) para. 2", "lender's lawyer/notary, payable by borrower"),
    "insurance": (True, "ON_191_08", "s. 5(1) para. 3", "insurance not excluded by s. 5(2)(a), (f), (h)"),
    "brokerage_reimbursed": (True, "ON_191_08", "s. 5(1) para. 4", "brokerage charge paid by lender, reimbursed by borrower"),
    "appraisal_required": (True, "ON_191_08", "s. 5(1) para. 5", "appraisal/inspection/survey required by lender"),
    "brokerage_fee": (True, "ON_188_08", "FSRA disclosure page", "brokerage fee charged to borrower (FSRA: include in cost of borrowing and APR)"),
    "default_insurance_pst": (True, "ON_191_08", "secondary source", "PST on default insurance premium (REMIC course text; "
                                                                  "the premium itself is excluded by s. 5(2)(h); confirm)"),
    "optional_insurance": (False, "ON_191_08", "s. 5(2)(a)", "optional insurance"),
    "overdraft": (False, "ON_191_08", "s. 5(2)(b)", "overdraft charges"),
    "registration": (False, "ON_191_08", "s. 5(2)(c)", "registration and registry search charges"),
    "prepayment_penalty": (False, "ON_191_08", "s. 5(2)(d)", "prepayment penalty"),
    "borrower_lawyer": (False, "ON_191_08", "s. 5(2)(e)", "borrower's own lawyer/notary"),
    "title_insurance": (False, "ON_191_08", "s. 5(2)(f)", "title insurance chosen and paid by borrower"),
    "appraisal_report_to_borrower": (False, "ON_191_08", "s. 5(2)(g)", "appraisal where borrower gets a shareable report"),
    "default_insurance": (False, "ON_191_08", "s. 5(2)(h)", "high-ratio default insurance premium"),
    "tax_account": (False, "ON_191_08", "s. 5(2)(i)", "tax account charges"),
    "discharge": (False, "ON_191_08", "s. 5(2)(j)", "discharge charges"),
    "default_charges": (False, "ON_191_08", "s. 5(2)(k)", "default charges"),
}


def periodic_rate(annual_rate_pct: float, compounding: str, per_year: int) -> float:
    """Effective rate per payment period, built on the shared monthly-rate helper."""
    return (1 + payments.monthly_rate(annual_rate_pct, compounding)) ** (12 / per_year) - 1


def restate(nominal_pct: float, from_per_year: int, to_per_year: int) -> float:
    """Convert a nominal annual rate between compounding frequencies."""
    eff = (1 + nominal_pct / 100 / from_per_year) ** from_per_year
    return (eff ** (1 / to_per_year) - 1) * to_per_year * 100


def amortization(principal: float, annual_rate_pct: float, amort_years: float, periods: int,
                 compounding: str = "semi", frequency: str = "monthly", payment: float | None = None) -> dict:
    """Payment schedule for the first ``periods`` payments; interest and payments rounded to cents."""
    ppy = FREQ[frequency]
    i = periodic_rate(annual_rate_pct, compounding, ppy)
    n = round(amort_years * ppy)
    if principal <= 0 or n <= 0 or periods <= 0:
        raise ValueError("principal, amortization and term must be positive")
    pmt = round(payment if payment else (principal / n if i == 0 else principal * i / (1 - (1 + i) ** -n)), 2)
    rows, bal = [], round(principal, 2)
    for k in range(1, periods + 1):
        if bal <= 0:
            break
        interest = round(bal * i, 2)
        if pmt <= interest and payment is None:
            raise ValueError("payment does not cover interest")
        pay = round(bal + interest, 2) if k == n else min(pmt, round(bal + interest, 2))
        closing = round(bal + interest - pay, 2)
        rows.append({"n": k, "opening": bal, "interest": interest, "principal": round(pay - interest, 2),
                     "payment": pay, "closing": closing})
        bal = closing
    return {"periodic_rate": i, "payment": pmt, "rows": rows}


def classify_charges(charges: list[dict]) -> tuple[list[dict], list[dict]]:
    included, excluded = [], []
    for c in charges or []:
        t = c.get("type")
        if t not in CHARGE_TYPES:
            raise ValueError(f"unknown charge type {t!r}; use one of {sorted(CHARGE_TYPES)}")
        inc, src, sec, desc = CHARGE_TYPES[t]
        item = {"type": t, "label": c.get("label") or desc, "amount": round(float(c.get("amount", 0)), 2),
                "basis": f"{src} {sec}"}
        (included if inc else excluded).append(item)
    return included, excluded


def apr_formula(cost: float, term_years: float, avg_principal: float) -> float:
    if term_years <= 0 or avg_principal <= 0:
        raise ValueError("term and average principal must be positive")
    return 100 * cost / (term_years * avg_principal)


def round_eighth(pct: float) -> float:
    return round(pct * 8) / 8


def cost_of_borrowing(principal: float, annual_rate: float, amort_years: float, term_months: int,
                      compounding: str = "semi", frequency: str = "monthly", charges: list[dict] | None = None,
                      payment: float | None = None, rate_type: str = "fixed") -> dict:
    """Total cost of borrowing over the term and the APR (O. Reg. 191/08 ss. 3-5), with the federal comparison."""
    if compounding not in COMP_PER_YEAR or frequency not in FREQ:
        raise ValueError("compounding must be semi|monthly and frequency monthly|biweekly|weekly")
    principal, annual_rate, ppy = float(principal), float(annual_rate), FREQ[frequency]
    periods = max(1, round(term_months * ppy / 12))
    sched = amortization(principal, annual_rate, amort_years, periods, compounding, frequency, payment)
    rows = sched["rows"]
    included, excluded = classify_charges(charges or [])
    interest = round(sum(r["interest"] for r in rows), 2)
    non_interest = round(sum(c["amount"] for c in included), 2)
    cost = round(interest + non_interest, 2)
    t_years = len(rows) / ppy
    avg_p = sum(r["opening"] for r in rows) / len(rows)
    raw = apr_formula(cost, t_years, avg_p)
    if non_interest == 0:
        apr, basis = annual_rate, "s. 4(1): interest is the only cost of borrowing, so APR = annual interest rate"
    else:
        apr = restate(raw, ppy, COMP_PER_YEAR[compounding])
        basis = (f"s. 3(1) formula restated to the quoted {compounding} compounding basis (s. 4(2) interpretation)"
                 if compounding == "semi" or ppy != 12 else "s. 3(1) formula")
    fed = {"apr_pct": round(raw, 4), "apr_rounded_eighth_pct": round_eighth(raw),
           "basis": "FCPF Regulations s. 47(1) formula; s. 47(2)(a) permits rounding to the nearest 1/8 %",
           "difference_vs_ontario_pts": round(raw - apr, 4) + 0.0}
    fed["materially_different"] = abs(fed["difference_vs_ontario_pts"]) >= 0.01
    out = {
        "rate_type": rate_type,
        "principal": round(principal, 2), "annual_rate_pct": annual_rate, "compounding": compounding,
        "frequency": frequency, "term_months": term_months, "term_years": round(t_years, 4),
        "payment": sched["payment"], "payments_in_term": len(rows),
        "total_payments": round(sum(r["payment"] for r in rows), 2),
        "interest_over_term": interest, "non_interest_charges": non_interest,
        "cost_of_borrowing": cost, "average_principal": round(avg_p, 2),
        "balance_at_maturity": rows[-1]["closing"],
        "apr_formula_pct": round(raw, 4), "apr_pct": round(apr, 4), "apr_rounded_eighth_pct": round_eighth(apr),
        "apr_basis": basis, "federal_comparison": fed,
        "included_charges": included, "excluded_charges": excluded, "schedule": rows,
        "assumptions": ["non-interest charges are paid at or before the advance and are not added to the principal",
                        "interest and payments are rounded to the cent each period"],
    }
    if rate_type == "variable":
        out["assumptions"].append("variable rate: the rate in effect on the calculation day is assumed for the whole "
                                  "term (s. 3(2)(d))")
    cites = [cite("ON_191_08", s) for s in ("s. 3", "s. 4", "s. 5")] + [cite("FCPF_REGS", "s. 47")]
    cites += [cite(c["basis"].split(" ", 1)[0], c["basis"].split(" ", 1)[1]) for c in included + excluded]
    return envelope(out, "disclosure.cost_of_borrowing", cites)


def trigger_rate(balance: float, payment: float, frequency: str = "monthly") -> float:
    """Annual rate (monthly compounding) at which a fixed payment no longer covers interest (s. 9(1) para. 6)."""
    i = payment / balance
    return ((1 + i) ** (FREQ[frequency] / 12) - 1) * 12 * 100


def _due_dates(first, frequency: str, count: int) -> list[str]:
    d0 = _d(first)
    if frequency == "monthly":
        out = []
        for k in range(count):
            y, m = divmod(d0.month - 1 + k, 12)
            yy, mm = d0.year + y, m + 1
            day = d0.day
            while True:
                try:
                    out.append(date(yy, mm, day).isoformat())
                    break
                except ValueError:
                    day -= 1
        return out
    step = 14 if frequency == "biweekly" else 7
    return [(d0 + timedelta(days=step * k)).isoformat() for k in range(count)]


# s. 8(1) items, in order, mapped to where the value comes from
S8_ITEMS = [
    (1, "Principal amount of the mortgage", "principal"),
    (2, "Amount and timing of each advance", "advances"),
    (3, "Total amount of all payments", "total_payments"),
    (4, "Cost of borrowing over the term, in dollars and cents", "cost_of_borrowing"),
    (5, "Term, and amortization period if different", "term_and_amortization"),
    (6, "Annual interest rate and compounding", "rate_and_compounding"),
    (7, "APR, if different from the annual interest rate", "apr"),
    (8, "Date interest starts to accrue and any interest-free periods", "interest_start_date"),
    (9, "Amount and due date of each payment", "payment_schedule"),
    (10, "How payments are applied", "payment_application"),
    (11, "Amortization schedule", "amortization_schedule"),
    (12, "Optional services accepted, their charges and cancellation terms", "optional_services"),
    (13, "Prepayment rights (Act s. 24(1)-(4))", "prepayment_terms"),
    (14, "s. 16(3) formula, if s. 16 applies", "s16_formula"),
    (15, "Prepayment penalties (Act s. 24(5)) and default charges (s. 17)", "penalties"),
    (16, "Property securing the mortgage", "property"),
    (17, "Brokerage charges included in the loan and paid by the lender", "brokerage_charges_paid_by_lender"),
    (18, "Discharge charge and its amount", "discharge_charge"),
    (19, "Any non-interest charges", "non_interest_charges"),
]
NOT_APPLICABLE_OK = {"s16_formula", "optional_services", "brokerage_charges_paid_by_lender"}


def disclosure_statement(a: dict) -> dict:
    """Initial disclosure statement (O. Reg. 191/08 s. 8(1); s. 9(1) additions for variable rates)."""
    cob = cost_of_borrowing(a["principal"], a["annual_rate"], a["amort_years"], int(a["term_months"]),
                            a.get("compounding", "semi"), a.get("frequency", "monthly"), a.get("charges"),
                            a.get("payment"), a.get("rate_type", "fixed"))
    freq = cob["frequency"]
    comp_words = {"semi": "compounded half-yearly, not in advance", "monthly": "compounded monthly, not in advance"}
    amort = a["amort_years"]
    v = {
        "principal": cob["principal"],
        "advances": a.get("advances") or ([{"amount": cob["principal"], "date": a["advance_date"]}]
                                          if a.get("advance_date") else None),
        "total_payments": cob["total_payments"],
        "cost_of_borrowing": cob["cost_of_borrowing"],
        "term_and_amortization": f"{a['term_months']} months; amortization {amort} years",
        "rate_and_compounding": f"{cob['annual_rate_pct']}% per year, {comp_words[cob['compounding']]}",
        "apr": None if cob["apr_pct"] == cob["annual_rate_pct"] else f"{cob['apr_pct']:.3f}%",
        "interest_start_date": a.get("interest_start_date") or a.get("advance_date"),
        "payment_schedule": ({"amount": cob["payment"], "frequency": freq, "count": cob["payments_in_term"],
                              "due_dates": _due_dates(a["first_payment_date"], freq, cob["payments_in_term"])}
                             if a.get("first_payment_date") else None),
        "payment_application": a.get("payment_application") or "each payment is applied first to interest, then to principal",
        "amortization_schedule": f"{cob['payments_in_term']} rows attached",
        "optional_services": a.get("optional_services"),
        "prepayment_terms": a.get("prepayment_terms"),
        "s16_formula": a.get("s16_formula"),
        "penalties": a.get("penalties"),
        "property": a.get("property"),
        "brokerage_charges_paid_by_lender": a.get("brokerage_charges_paid_by_lender"),
        "discharge_charge": a.get("discharge_charge"),
        "non_interest_charges": cob["included_charges"] + cob["excluded_charges"],
    }
    items = []
    for num, label, key in S8_ITEMS:
        val = v[key]
        status = "provided" if val not in (None, "", []) else ("not applicable?" if key in NOT_APPLICABLE_OK
                                                                else "missing")
        if key == "apr" and val is None:
            status, val = "provided", "same as annual interest rate (s. 4(1))"
        if key == "non_interest_charges" and val == []:
            status, val = "provided", "none"
        items.append({"item": num, "label": label, "value": val, "status": status})
    if cob["rate_type"] == "variable":
        items += [
            {"item": "9(1)2", "label": "Rate in effect on the statement date", "value": f"{cob['annual_rate_pct']}%",
             "status": "provided"},
            {"item": "9(1)3", "label": "How and when later rates are determined", "value": a.get("rate_adjustment_method"),
             "status": "provided" if a.get("rate_adjustment_method") else "missing"},
            {"item": "9(1)6", "label": "Rate above which payments no longer cover interest (negative amortization possible)",
             "value": f"{trigger_rate(cob['principal'], cob['payment'], freq):.3f}% (monthly compounding)",
             "status": "provided"},
        ]
    if a.get("statement_date"):
        due = (a.get("signing_date"), a.get("payment_date"), a.get("obligation_date"))
        if any(due):
            timing = delivery_timing(a["statement_date"], *due, waiver_date=a.get("waiver_date"))
            cob_timing = {k: timing[k] for k in ("ok", "earliest_event", "business_days", "latest_compliant_date",
                                                 "waiver_valid", "finding")}
        else:
            cob_timing = {"ok": None, "finding": "no signing, payment or obligation date given"}
    else:
        cob_timing = None
    stmt = {
        "title": "Mortgage cost of borrowing disclosure statement",
        "borrower": a.get("borrower"), "lender": a.get("lender"), "brokerage": a.get("brokerage"),
        "statement_date": a.get("statement_date"),
        "items": items,
        "missing": [f"{i['item']}. {i['label']}" for i in items if i["status"] == "missing"],
        "timing": cob_timing,
        "cost": {k: cob[k] for k in ("principal", "payment", "total_payments", "interest_over_term",
                                     "non_interest_charges", "cost_of_borrowing", "balance_at_maturity", "apr_pct",
                                     "apr_formula_pct", "apr_basis", "federal_comparison", "assumptions")},
        "schedule": cob["schedule"],
    }
    stmt["text"] = render_text(stmt)
    cites = cob["citations"] + [cite("ON_191_08", "s. 8(1)"), cite("ON_191_08", "s. 6")]
    if cob["rate_type"] == "variable":
        cites.append(cite("ON_191_08", "s. 9(1)"))
    if cob_timing:
        cites.append(cite("ON_191_08", "s. 7"))
    return envelope(stmt, "disclosure.statement", cites)


def _fmt(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"${v:,.2f}"
    if isinstance(v, list):
        return "; ".join(_fmt(x) for x in v) or "none"
    if isinstance(v, dict):
        if "due_dates" in v:
            dd = v["due_dates"]
            return f"${v['amount']:,.2f} {v['frequency']}, {v['count']} payments, {dd[0]} to {dd[-1]}"
        if "date" in v and "amount" in v:
            return f"${float(v['amount']):,.2f} on {v['date']}"
        if "label" in v:
            return f"{v['label']} ${v['amount']:,.2f} ({v['basis']})"
        return ", ".join(f"{k}: {_fmt(x)}" for k, x in v.items())
    return "" if v is None else str(v)


def render_text(stmt: dict) -> str:
    """Plain-text rendering of a disclosure statement (s. 6(4): clear, concise, logically presented)."""
    head = [stmt["title"].upper()]
    for k in ("borrower", "lender", "brokerage", "statement_date"):
        if stmt.get(k):
            head.append(f"{k.replace('_', ' ').title()}: {stmt[k]}")
    lines = head + [""]
    for it in stmt["items"]:
        flag = "" if it["status"] == "provided" else f"  [{it['status'].upper()}]"
        lines.append(f"{it['item']}. {it['label']}: {_fmt(it['value'])}{flag}")
    c = stmt["cost"]
    lines += ["", f"Interest over the term: ${c['interest_over_term']:,.2f}",
              f"Non-interest charges in the cost of borrowing: ${c['non_interest_charges']:,.2f}",
              f"Balance owing at the end of the term: ${c['balance_at_maturity']:,.2f}",
              f"APR: {c['apr_pct']:.3f}% ({c['apr_basis']})",
              f"Federal formula APR for comparison: {c['federal_comparison']['apr_pct']:.3f}%"]
    if stmt.get("missing"):
        lines += ["", "MISSING BEFORE DELIVERY: " + "; ".join(stmt["missing"])]
    return "\n".join(lines)


def delivery_timing(statement_date, signing_date=None, payment_date=None, obligation_date=None,
                    waiver_date=None, jurisdiction: str = "ON", extra_holidays: list | None = None) -> dict:
    """O. Reg. 191/08 s. 7 (and 188/08 s. 35): statement at least two business days before the earliest of
    first payment, signing, or incurring any obligation, unless the borrower waived in writing before then."""
    events = {k: _d(v) for k, v in (("payment", payment_date), ("signing", signing_date),
                                    ("obligation", obligation_date)) if v}
    if not events:
        raise ValueError("give at least one of signing_date, payment_date, obligation_date")
    kind, first = min(events.items(), key=lambda kv: kv[1])
    sd = _d(statement_date)
    bd = business_days_between(sd, first, jurisdiction, extra_holidays)
    latest = latest_date_with_business_days_before(first, 2, jurisdiction, extra_holidays)
    waiver_valid = bool(waiver_date) and _d(waiver_date) < first
    if sd >= first:
        ok, finding = False, f"statement given on or after the {kind} date; disclosure must come first"
    elif bd >= 2:
        ok, finding = True, f"{bd} business days before {kind}"
    elif waiver_valid:
        ok, finding = True, "two-business-day period waived in writing before the earliest event (s. 7(2))"
    else:
        ok, finding = False, (f"only {bd} business day(s) before {kind}; deliver by {latest.isoformat()} or obtain "
                              "a written waiver before the earliest event")
    out = {"ok": ok, "earliest_event": kind, "earliest_event_date": first.isoformat(), "business_days": bd,
           "latest_compliant_date": latest.isoformat(), "waiver_valid": waiver_valid, "finding": finding,
           "assumptions": ["business day = not a Saturday or Ontario holiday (Legislation Act s. 88); first day "
                           "excluded, last day counted"]}
    return envelope(out, "disclosure.delivery_timing",
                    [cite("ON_191_08", "s. 7"), cite("ON_188_08", "s. 35"), cite("ON_LEGISLATION_ACT", "ss. 88-89")])

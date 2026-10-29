"""Servicing Desk tools: the ``decision_ladder.servicing`` engines exposed to Nemotron and the desk UI.

No AppModule is registered: the registry's modules are vendored projects under ``modules/<dir>``, and the
Servicing Desk is native code with its UI at ``/desks/servicing.html``. Tools are added with
``add_tool(tool, None)`` and given the "servicing" stage in the router's stage map. Calculators already exposed elsewhere are not duplicated: ``prepayment_savings``
(monthly extra + annual lump, no dates or privileges) and ``refinance_cash_out`` (80% LTV equity take-out)
stay in ``jsapps``; the tools here add dated schedules, every frequency, privileges, blends, ports, HELOC
room and deferrals.
"""
from __future__ import annotations

from datetime import date

from ..agent.router import CORE_STAGE
from ..agent.tools import Tool, _obj
from ..servicing import blend as BL
from ..servicing import deferral as DF
from ..servicing import frequency as F
from ..servicing import heloc as HE
from ..servicing import prepayment as PP
from ..servicing import schedule as SC
from .registry import add_tool

N = {"type": "number"}
I = {"type": "integer"}
B = {"type": "boolean"}
S = {"type": "string"}
DATE = {"type": "string", "description": "YYYY-MM-DD"}
DATES = {"type": "array", "items": DATE}
FREQ = {"type": "string", "enum": list(F.FREQUENCIES),
        "description": "payment frequency; accelerated = monthly payment / 2 (26 a year) or / 4 (52 a year)"}
RATE_TYPE = {"type": "string", "enum": ["fixed", "variable"],
             "description": "fixed compounds semi-annually, variable monthly"}
ENGINE = "decision_ladder.servicing"

LOAN = {
    "principal": {"type": "number", "description": "loan amount or current balance, dollars"},
    "annual_rate": {"type": "number", "description": "contract rate, percent (5.25 = 5.25%)"},
    "amort_years": {"type": "number", "description": "amortization remaining, years"},
    "frequency": FREQ, "rate_type": RATE_TYPE,
    "funding_date": {"type": "string", "description": "YYYY-MM-DD the loan funded (or the statement date); "
                                                       "first payment is one period later. Default today"},
    "first_payment_date": {"type": "string", "description": "YYYY-MM-DD, overrides funding_date"},
    "rate_changes": {"type": "array", "description": "mid-term rate changes, percent",
                     "items": _obj({"date": DATE, "rate": N}, ["date", "rate"])},
    "variable_payment": {"type": "string", "enum": ["fixed", "adjustable"],
                         "description": "variable only: payment held (trigger rate applies) or re-amortized at each change"},
    "term_months": {"type": "integer", "description": "term length in months; stops the schedule at maturity"},
    "payment": {"type": "number", "description": "actual regular payment in dollars, if different from the computed one"},
    "trigger_point_pct": {"type": "number", "description": "balance as % of original principal at which the lender "
                                                           "acts (default 100; contract term)"},
    "on_trigger_point": {"type": "string", "enum": ["flag", "reset"]},
}
LOAN_REQ = ["principal", "annual_rate", "amort_years"]
PENALTY = {
    "lender": {"type": "string", "description": "penalty profile code: generic, rbc, rbc_pv, td, scotia, cibc, bmo, nbc"},
    "comparison_posted_rate": {"type": "number", "description": "lender's current rate for the remaining term, percent"},
    "discount": {"type": "number", "description": "documented original rate discount, percentage points"},
    "penalty_method": {"type": "string", "enum": ["simple_differential", "posted_minus_discount", "cibc_discount_addback",
                                                  "present_value"],
                       "description": "IRD family when the lender profile does not fix one"},
}


def _d(s: str | None) -> date | None:
    return date.fromisoformat(str(s)[:10]) if s else None


def _loan(a: dict) -> SC.LoanSpec:
    freq = a.get("frequency", "monthly")
    first = _d(a.get("first_payment_date")) or F.first_payment_after(_d(a.get("funding_date")) or date.today(), freq)
    return SC.LoanSpec(
        principal=float(a["principal"]), annual_rate=float(a["annual_rate"]), amort_years=float(a["amort_years"]),
        first_payment=first, frequency=freq, rate_type=a.get("rate_type", "fixed"),
        rate_changes=[(_d(c["date"]), float(c["rate"])) for c in a.get("rate_changes", [])],
        variable_payment=a.get("variable_payment", "fixed"), term_months=a.get("term_months"),
        payment=a.get("payment"), trigger_point_pct=float(a.get("trigger_point_pct", 100.0)),
        on_trigger_point=a.get("on_trigger_point", "flag"))


def _terms(a: dict) -> PP.PenaltyTerms:
    return PP.PenaltyTerms(lender=a.get("lender", "generic"), comparison_posted_rate=a.get("comparison_posted_rate"),
                           documented_discount=a.get("discount"), method=a.get("penalty_method"))


def _tag(out: dict, method: str) -> dict:
    out["engine"] = ENGINE
    out["method"] = method
    return out


# ------------------------------------------------------------------------------------------- tools
def t_schedule(a: dict) -> dict:
    sch = SC.build(_loan(a))
    return _tag(sch.as_dict(rows=bool(a.get("rows"))),
                "dated amortization; fixed = semi-annual compounding, variable = monthly; periodic rate equivalent "
                "for the frequency; interest split by days across rate changes")


def t_frequencies(a: dict) -> dict:
    funding = _d(a.get("funding_date")) or date.today()
    rt = a.get("rate_type", "fixed")
    rows = SC.compare_frequencies(float(a["principal"]), float(a["annual_rate"]), float(a["amort_years"]), funding, rt)
    return _tag({"funding_date": funding.isoformat(), "frequencies": rows},
                "every frequency funded the same day and run to payoff; accelerated = monthly payment / 2 or / 4")


def t_trigger(a: dict) -> dict:
    freq, bal, pmt = a.get("frequency", "monthly"), float(a["balance"]), float(a["payment"])
    tr = SC.trigger_rate(bal, pmt, freq, "monthly")
    out = {"balance": bal, "payment": pmt, "frequency": freq, "trigger_rate": round(tr, 4),
           "interest_at_trigger_rate": round(bal * F.periodic_rate(tr, F.get(freq).per_year, "monthly"), 2)}
    if a.get("current_rate") is not None:
        cur = float(a["current_rate"])
        interest = bal * F.periodic_rate(cur, F.get(freq).per_year, "monthly")
        out.update(current_rate=cur, headroom_pts=round(tr - cur, 4), interest_now=round(interest, 2),
                   principal_now=round(pmt - interest, 2), above_trigger=interest > pmt)
    return _tag(out, "trigger rate = annual rate (monthly compounding) whose periodic interest on the balance "
                     "equals the payment")


def t_prepay(a: dict) -> dict:
    spec = _loan(a)
    ev = SC.Events(prepayments=[(_d(p["date"]), float(p["amount"])) for p in a.get("lump_sums", [])],
                   payment_changes=[(_d(p["date"]), spec.scheduled_payment() * (1 + float(p["increase_pct"]) / 100))
                                    for p in a.get("payment_increases", [])],
                   double_ups=[_d(x) for x in a.get("double_ups", [])])
    priv = PP.Privileges(lump_sum_pct=float(a.get("lump_sum_pct", 15)),
                         payment_increase_pct=float(a.get("payment_increase_pct", 15)),
                         double_up=bool(a.get("double_up_allowed", True)),
                         double_up_counts_toward_lump=bool(a.get("double_up_counts_toward_lump", False)),
                         year_basis=a.get("year_basis", "anniversary"))
    return _tag(PP.prepayment_plan(spec, ev, priv, _terms(a), rows=bool(a.get("rows"))),
                "schedule with and without prepayments; privileges per privilege year; overages priced by the "
                "Decimal penalty engine on the excess only")


def _current(a: dict) -> BL.Current:
    return BL.Current(balance=float(a["balance"]), rate=float(a["current_rate"]),
                      remaining_term_months=int(a["remaining_term_months"]),
                      remaining_amort_years=float(a["remaining_amort_years"]),
                      as_of=_d(a.get("as_of")) or date.today(), rate_type=a.get("rate_type", "fixed"),
                      frequency=a.get("frequency", "monthly"))


def t_blend(a: dict) -> dict:
    out = BL.blend_vs_break(_current(a), float(a["new_rate"]), int(a["new_term_months"]),
                            new_funds=float(a.get("new_funds", 0)), horizon_months=a.get("horizon_months"),
                            renewal_rate=a.get("renewal_rate"), terms=_terms(a), penalty_override=a.get("penalty"),
                            refinance_costs=float(a.get("refinance_costs", 0)),
                            capitalize_penalty=bool(a.get("capitalize_penalty", False)),
                            refinance_amort_years=a.get("refinance_amort_years"), property_value=a.get("property_value"))
    return _tag(out, BL.BLEND_METHOD)


def t_port(a: dict) -> dict:
    out = BL.port_and_increase(_current(a), float(a["new_funds"]), float(a["new_rate"]),
                               new_term_months=a.get("new_term_months"), new_amort_years=a.get("new_amort_years"),
                               sale_closing=_d(a.get("sale_closing")), purchase_closing=_d(a.get("purchase_closing")),
                               port_window_days=a.get("port_window_days"), purchase_price=a.get("purchase_price"),
                               terms=_terms(a))
    out["engine"] = ENGINE
    return out


def t_heloc(a: dict) -> dict:
    segs = a.get("amortizing") or []
    out = HE.readvanceable(float(a["property_value"]), segs, float(a.get("heloc_balance", 0)), float(a["heloc_rate"]),
                           authorized_limit=a.get("authorized_limit"), as_of=_d(a.get("as_of")),
                           basis=a.get("interest_basis", "actual_365"),
                           projection_years=int(a.get("projection_years", 0)))
    out["source"] = HE.OSFI_SOURCE["url"]
    return _tag(out, "revolving limit = min(65% x value, 80% x value - amortizing balances), capped by the authorized "
                     "limit; minimum payment interest-only")


def t_deferral(a: dict) -> dict:
    out = DF.defer_payments(_loan(a), _d(a.get("start")) or date.today(), int(a["n_payments"]), rows=bool(a.get("rows")))
    out["engine"] = ENGINE
    return out


def t_arrears(a: dict) -> dict:
    out = DF.arrears(float(a["payment"]), float(a["annual_rate"]), int(a["missed"]), a.get("frequency", "monthly"),
                     a.get("rate_type", "fixed"), float(a.get("fees_per_missed", 0)))
    out["engine"] = ENGINE
    return out


CURRENT = {
    "balance": {"type": "number", "description": "current balance, dollars"},
    "current_rate": {"type": "number", "description": "current contract rate, percent"},
    "remaining_term_months": {"type": "integer", "description": "months left on the current term"},
    "remaining_amort_years": {"type": "number", "description": "years left on the amortization"},
    "as_of": DATE, "rate_type": RATE_TYPE, "frequency": FREQ,
}
CURRENT_REQ = ["balance", "current_rate", "remaining_term_months", "remaining_amort_years"]

TOOLS = [
    Tool("servicing_schedule",
         "Dated amortization schedule for a Canadian mortgage at any frequency (monthly, semi-monthly, bi-weekly, "
         "accelerated bi-weekly, weekly, accelerated weekly). Fixed (semi-annual) or variable (monthly compounding) with "
         "mid-term rate changes [{date, rate}]; variable_payment='fixed' holds the payment and reports the trigger rate, "
         "the first date the rate exceeds it, and the trigger point (balance above trigger_point_pct of the original). "
         "Returns a summary (payment, payoff date, total interest in dollars, balance at term maturity) and calendar-year "
         "totals; rows=true adds every dated payment.",
         _obj({**LOAN, "rows": B}, LOAN_REQ), t_schedule, "servicing"),
    Tool("servicing_frequency_compare",
         "Payment, annual outlay, payoff date and total interest (dollars) for all six Canadian payment frequencies, "
         "funded the same day; shows what accelerated bi-weekly/weekly save vs monthly.",
         _obj({k: LOAN[k] for k in ("principal", "annual_rate", "amort_years", "rate_type", "funding_date")}, LOAN_REQ),
         t_frequencies, "servicing"),
    Tool("variable_trigger_rate",
         "Trigger rate for a fixed-payment variable mortgage from the balance and regular payment (dollars): the annual "
         "rate (percent, monthly compounding) at which the payment only covers interest. With current_rate, also the "
         "headroom in percentage points and the interest/principal split today.",
         _obj({"balance": N, "payment": N, "frequency": FREQ, "current_rate": N}, ["balance", "payment"]),
         t_trigger, "servicing"),
    Tool("servicing_prepayment",
         "Prepayment plan on a dated schedule: lump sums [{date, amount}], payment increases [{date, increase_pct}] and "
         "double-up dates, against the contract privileges (lump_sum_pct of original principal per privilege year, "
         "payment_increase_pct of the original payment, double-ups). Returns interest saved (dollars), time saved, "
         "remaining privilege room per year, flags, and any overage priced with the penalty engine (needs term_months; "
         "fixed-rate IRD needs comparison_posted_rate and a lender or penalty_method). Unlike prepayment_savings this "
         "handles dates, every frequency and privileges.",
         _obj({**LOAN, **PENALTY,
               "lump_sums": {"type": "array", "items": _obj({"date": DATE, "amount": N}, ["date", "amount"])},
               "payment_increases": {"type": "array", "items": _obj({"date": DATE, "increase_pct": N},
                                                                     ["date", "increase_pct"])},
               "double_ups": DATES, "lump_sum_pct": N, "payment_increase_pct": N, "double_up_allowed": B,
               "double_up_counts_toward_lump": B,
               "year_basis": {"type": "string", "enum": ["anniversary", "calendar"]}, "rows": B}, LOAN_REQ),
         t_prepay, "servicing"),
    Tool("blend_vs_break",
         "Blend-and-extend and/or blend-and-increase (new_funds) vs staying vs breaking and refinancing, ranked by cost "
         "over a common horizon (dollars: payments + up-front cash + balance at horizon - money borrowed). Blended rate "
         "is weighted by amount and remaining term. Break penalty from the penalty engine (or 'penalty' in dollars). "
         "Options ending before the horizon renew at renewal_rate (default new_rate).",
         _obj({**CURRENT, **PENALTY, "new_rate": N, "new_term_months": I, "new_funds": N, "horizon_months": I,
               "renewal_rate": N, "penalty": N, "refinance_costs": N, "capitalize_penalty": B,
               "refinance_amort_years": N, "property_value": N},
              CURRENT_REQ + ["new_rate", "new_term_months"]), t_blend, "servicing"),
    Tool("port_and_increase",
         "Port a fixed mortgage to a new home and add new_funds: blended rate (amount and time weighted), new payment vs "
         "old, LTV on the purchase, the penalty porting avoids, and port-window checks from the sale and purchase "
         "closing dates.",
         _obj({**CURRENT, **PENALTY, "new_funds": N, "new_rate": N, "new_term_months": I, "new_amort_years": N,
               "sale_closing": DATE, "purchase_closing": DATE, "port_window_days": I, "purchase_price": N},
              CURRENT_REQ + ["new_funds", "new_rate"]), t_port, "servicing"),
    Tool("heloc_room",
         "Readvanceable mortgage / HELOC room under OSFI B-20: revolving portion capped at 65% of value, whole plan at "
         "80%. Returns combined and revolving LTV (percent), revolving limit and available room (dollars), interest-only "
         "minimum payment, flags, and optionally a yearly readvance projection as the amortizing segments pay down "
         "(segments need rate and amort_years).",
         _obj({"property_value": N, "heloc_balance": N,
               "heloc_rate": {"type": "number", "description": "HELOC rate, percent (prime + spread)"},
               "amortizing": {"type": "array", "items": _obj({"label": S, "balance": N, "rate": N, "amort_years": N,
                                                               "rate_type": RATE_TYPE, "frequency": FREQ}, ["balance"])},
               "authorized_limit": N, "as_of": DATE,
               "interest_basis": {"type": "string", "enum": ["actual_365", "monthly"]}, "projection_years": I},
              ["property_value", "heloc_rate"]), t_heloc, "servicing"),
    Tool("payment_deferral",
         "Skip n_payments regular payments from start: interest capitalized (dollars), balance after, and two ways back "
         "(keep the payment and pay longer, or re-amortize to the original payoff date) with extra interest for each.",
         _obj({**LOAN, "start": DATE, "n_payments": I, "rows": B}, LOAN_REQ + ["n_payments"]), t_deferral, "servicing"),
    Tool("mortgage_arrears",
         "Amount to bring a mortgage current after missed payments: payments due, interest on arrears at the mortgage "
         "rate, fees per missed payment (dollars).",
         _obj({"payment": N, "annual_rate": N, "missed": I, "frequency": FREQ, "rate_type": RATE_TYPE,
               "fees_per_missed": N}, ["payment", "annual_rate", "missed"]), t_arrears, "servicing"),
]
for _t in TOOLS:
    add_tool(_t, None)
    # no AppModule carries these tools, so give the router their lifecycle stage directly
    CORE_STAGE[_t.name] = ["servicing", "closing"] if _t.name == "port_and_increase" else ["servicing"]

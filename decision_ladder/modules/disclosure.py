"""Disclosure & Compliance Desk tools for the Mortgage OS.

Registered with ``add_tool(tool, None)``: the desk is in-repo code (``decision_ladder/disclosure``), not a vendored
project under ``modules/<dir>``, so no AppModule is added; the router's lifecycle stages come from ``STAGES`` below.
Its UI is ``/static/desks/disclosure.html``.
"""
from __future__ import annotations

from ..agent.router import CORE_STAGE
from ..agent.tools import Tool, _obj
from ..disclosure import conduct, cost_of_borrowing as cob, fintrac, interest_act, renewal
from ..disclosure.sources import SOURCES, envelope
from .registry import add_tool

N, I, B, S = {"type": "number"}, {"type": "integer"}, {"type": "boolean"}, {"type": "string"}
D = {"type": "string", "description": "YYYY-MM-DD"}
OBJ, ARR = {"type": "object"}, {"type": "array", "items": {"type": "object"}}
CHARGES = {"type": "array", "description": "non-interest charges; type is one of " + ", ".join(sorted(cob.CHARGE_TYPES)),
           "items": _obj({"type": S, "amount": N, "label": S}, ["type", "amount"])}
LOAN = {"principal": N, "annual_rate": {"type": "number", "description": "percent, e.g. 5.29"}, "amort_years": N,
        "term_months": I, "compounding": {"type": "string", "enum": ["semi", "monthly"]},
        "frequency": {"type": "string", "enum": sorted(cob.FREQ)}, "payment": N, "charges": CHARGES,
        "rate_type": {"type": "string", "enum": ["fixed", "variable"]}}
LOAN_REQ = ["principal", "annual_rate", "amort_years", "term_months"]


def t_cost(a: dict) -> dict:
    out = cob.cost_of_borrowing(a["principal"], a["annual_rate"], a["amort_years"], int(a["term_months"]),
                                a.get("compounding", "semi"), a.get("frequency", "monthly"), a.get("charges"),
                                a.get("payment"), a.get("rate_type", "fixed"))
    if not a.get("include_schedule"):
        out.pop("schedule")
    return out


def t_timing(a: dict) -> dict:
    return cob.delivery_timing(a["statement_date"], a.get("signing_date"), a.get("payment_date"),
                               a.get("obligation_date"), a.get("waiver_date"), a.get("jurisdiction", "ON"),
                               a.get("holidays"))


def t_conduct(a: dict) -> dict:
    return conduct.evaluate(a.get("file") or {}, a.get("jurisdiction", "ON"))


def t_rules(a: dict) -> dict:
    return envelope({"rules": conduct.rules_table(a.get("jurisdiction")), "sources": SOURCES},
                    "disclosure.rules", [])


TOOLS = [
    Tool("disclosure_cost_of_borrowing",
         "Ontario O. Reg. 191/08 cost of borrowing over the term and APR (s. 3 formula, s. 4 rules, s. 5 included and "
         "excluded charges), with the federal FCPF s. 47 APR for comparison. include_schedule=true adds the payment rows.",
         _obj({**LOAN, "include_schedule": B}, LOAN_REQ), t_cost, "compliance"),
    Tool("disclosure_statement",
         "Build the O. Reg. 191/08 s. 8(1) initial disclosure statement (s. 9(1) additions for variable rates) as items "
         "plus plain text, listing missing items and checking the two-business-day delivery rule when dates are given.",
         _obj({**LOAN, "borrower": S, "lender": S, "brokerage": S, "statement_date": D, "advance_date": D,
               "interest_start_date": D, "first_payment_date": D, "signing_date": D, "payment_date": D,
               "obligation_date": D, "waiver_date": D, "property": S, "prepayment_terms": S, "penalties": S,
               "discharge_charge": N, "optional_services": S, "brokerage_charges_paid_by_lender": N,
               "payment_application": S, "rate_adjustment_method": S, "s16_formula": S, "advances": ARR},
              LOAN_REQ), cob.disclosure_statement, "compliance"),
    Tool("disclosure_delivery_timing",
         "Two-business-day rule (O. Reg. 191/08 s. 7, 188/08 s. 35): was the statement delivered at least two business "
         "days (Ontario holidays) before the earliest of signing, first payment or any obligation, or validly waived?",
         _obj({"statement_date": D, "signing_date": D, "payment_date": D, "obligation_date": D, "waiver_date": D,
               "jurisdiction": S, "holidays": {"type": "array", "items": D}}, ["statement_date"]), t_timing, "compliance"),
    Tool("interest_act_check",
         "Interest Act ss. 6-10 on mortgage terms: rate statement (yearly/half-yearly, not in advance), payment-implied "
         "rate vs stated rate (s. 7), arrears charges (s. 8), and the five-year three-months'-interest right (s. 10).",
         _obj({"blended_payments": B, "principal_stated": B, "rate_stated": B, "stated_rate_pct": N,
               "stated_compounding": {"type": "string", "enum": ["yearly", "half-yearly", "monthly", "in advance"]},
               "equivalent_rate_stated": B, "in_advance": B, "principal": N, "payment": N, "amort_years": N,
               "frequency": S, "term_months": I, "mortgage_date": D, "maturity_date": D, "borrower_type": S,
               "balance_at_five_years": N, "penalty_after_five_years": N,
               "prepayment_clause": {"type": "string", "enum": ["open", "closed", "ird", "greater_of_3m_ird",
                                                                "three_months_interest"]},
               "renewal_or_extension": B, "arrears_rate_pct": N, "arrears_penalty": S}), interest_act.check,
         "compliance"),
    Tool("conduct_checklist",
         "Suitability and conflict-of-interest checklist for a borrower file: Ontario O. Reg. 188/08 (ss. 10-11, 18-27, "
         "35, 37) with FSRA MB0054INT, or Alberta RECA Rules (ss. 41, 43, 45, 65, 71, 72, 74, 75). Returns each rule's "
         "status and the missing fields. Call disclosure_rules to see the field names.",
         _obj({"jurisdiction": {"type": "string", "enum": ["ON", "AB"]}, "file": OBJ}, ["file"]), t_conduct, "compliance"),
    Tool("disclosure_rules", "The conduct rules table (citations and the file fields each rule reads) and the source "
         "registry with URLs and check dates.", _obj({"jurisdiction": S}), t_rules, "compliance"),
    Tool("fintrac_check",
         "FINTRAC identification and record-keeping check for a mortgage file: identity method details (photo ID, "
         "credit file, dual-process, reliance), information record, beneficial owners, PEP/HIO and third-party "
         "determinations, large cash/virtual currency (24-hour rule), receipt of funds, compliance program, 5-year "
         "retention date.",
         _obj({"clients": ARR, "transactions": ARR, "program": OBJ, "record_date": D, "as_of": D}, ["clients"]),
         fintrac.check, "compliance"),
    Tool("renewal_disclosure_timing",
         "Renewal statement timing: federal banks (FCPF Regulations s. 45, 21 days, Interpretation Act counting) or "
         "Ontario brokerage-lender (O. Reg. 191/08 s. 14), the date the renewal can take effect, missing content, "
         "non-renewal notice, and optional renewal cost of borrowing.",
         _obj({"maturity_date": D, "statement_date": D, "received_date": D,
               "regime": {"type": "string", "enum": ["federal_bank", "ontario_lender"]}, "brokerage_is_lender": B,
               "will_not_renew": B, "notice_date": D, "includes_cost_information": B,
               "includes_no_increase_statement": B, "includes_rights_statement": B, "renewal_terms": OBJ},
              ["maturity_date"]), renewal.check, "compliance"),
]
STAGES = {"disclosure_cost_of_borrowing": ["compliance", "closing"], "disclosure_statement": ["compliance", "closing"],
          "disclosure_delivery_timing": ["compliance", "closing"], "interest_act_check": ["compliance", "servicing"],
          "conduct_checklist": ["compliance", "underwriting"], "disclosure_rules": ["compliance"],
          "fintrac_check": ["compliance", "documents"], "renewal_disclosure_timing": ["compliance", "servicing"]}
for _t in TOOLS:
    add_tool(_t, None)
    CORE_STAGE.setdefault(_t.name, STAGES[_t.name])

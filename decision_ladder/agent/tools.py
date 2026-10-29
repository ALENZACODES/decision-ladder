"""The tool belt Nemotron is allowed to use.

Every tool is a thin JSON wrapper around a tested deterministic engine. The model chooses *which* tool to
call and with *what* arguments; it never produces a mortgage number on its own. Tool results are recorded
in a ledger so the provenance verifier (``verify.py``) can check every figure in the final answer.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from ..engines import (affordability, guardrail, homevalue, insurance, ird, kyc, lenders, payments, qualify,
                       ratebook, renewal)
from ..penalty.models import PenaltyInputs
from ..penalty.engine import calculate_penalty
from ..penalty.workbench import WorkbenchCase, run_workbench
from ..penalty.methods import all_specs

LENDER_CODES = {"RBC": "rbc", "TD": "td", "Scotiabank": "scotia", "CIBC": "cibc", "BMO": "bmo",
                "National Bank": "nbc"}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable[[dict], Any]
    rung: str = "general"

    def spec(self) -> dict:
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": self.parameters}}


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


N = {"type": "number"}
I = {"type": "integer"}
B = {"type": "boolean"}
S = {"type": "string"}

FILE_PROPS = {
    "price": {"type": "number", "description": "purchase price, dollars"},
    "down_payment": {"type": "number", "description": "down payment, dollars"},
    "annual_income": {"type": "number", "description": "gross household income, dollars per year"},
    "contract_rate": {"type": "number", "description": "mortgage rate in percent, e.g. 4.29"},
    "property_tax_annual": N, "heat_annual": N, "condo_fees_monthly": N,
    "other_debt_monthly": {"type": "number", "description": "car, card, loan payments per month"},
    "amort_years": I, "first_time_buyer": B, "new_build": B,
}
FILE_REQ = ["price", "down_payment", "annual_income", "contract_rate"]


def _jsonable(x: Any) -> Any:
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if hasattr(x, "to_dict"):
        return _jsonable(x.to_dict())
    return x


def _date(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


# ---------------------------------------------------------------- tool functions
def t_qualify(a: dict) -> dict:
    return qualify.qualify(**a).to_dict()


def t_insurance(a: dict) -> dict:
    return insurance.premium(**a).to_dict()


def t_remediate(a: dict) -> dict:
    return affordability.remediation_options(a)


def t_max_price(a: dict) -> dict:
    return affordability.max_purchase_price(a)


def t_payment(a: dict) -> dict:
    comp = "monthly" if a.get("variable") else "semi"
    p = payments.payment(a["principal"], a["annual_rate"], a["amort_years"], comp)
    out = {"monthly_payment": round(p, 2), "compounding": "semi-annual (fixed)" if comp == "semi" else "monthly (variable)"}
    if a.get("months_paid"):
        out["balance_after"] = round(payments.balance_after(a["principal"], a["annual_rate"], a["amort_years"],
                                                            int(a["months_paid"]), comp), 2)
    return out


def t_penalty_simple(a: dict) -> dict:
    a = dict(a)
    new_rate, am = a.pop("new_rate", None), a.pop("amort_years_remaining", None)
    p = ird.penalty(**a)
    out = {"penalty": p.to_dict()}
    if new_rate is not None and am is not None:
        out["refinance"] = ird.refinance_analysis(balance=a["balance"], current_rate=a["contract_rate"], new_rate=new_rate,
                                                  months_remaining=a["months_remaining"], amort_years_remaining=am,
                                                  penalty_amount=p.penalty)
    return out


def t_penalty_lender(a: dict) -> dict:
    """Lender-method penalty using the bank's own posted-rate table from the rate book."""
    bank = ratebook.canonical_bank(a["lender"])
    code = LENDER_CODES.get(bank or "", "generic")
    posted = {}
    prov = None
    if bank:
        tbl = ratebook.bank_posted_table(bank, a.get("rates_as_of"))
        posted = {k: Decimal(str(v)) for k, v in tbl["posted"].items()}
        prov = tbl["provenance"]
    case = WorkbenchCase(
        lender=code, balance=Decimal(str(a["balance"])), contract_rate=Decimal(str(a["contract_rate"])),
        term_start=_date(a["term_start"]), maturity=_date(a["maturity"]),
        payout=_date(a.get("payout_date") or date.today().isoformat()), current_posted=posted,
        original_posted_rate=None if a.get("original_posted_rate") is None else Decimal(str(a["original_posted_rate"])),
        contract_discount=None if a.get("contract_discount") is None else Decimal(str(a["contract_discount"])),
        cashback=Decimal(str(a.get("cashback", 0))), discharge_fee=Decimal(str(a.get("discharge_fee", 0))),
        rate_type=a.get("rate_type", "fixed"))
    res = run_workbench(case).as_dict()
    res["lender_code"] = code
    res["posted_rate_provenance"] = prov
    return _jsonable(res)


def t_penalty_engine(a: dict) -> dict:
    inp = PenaltyInputs(balance=Decimal(str(a["balance"])), annual_rate=Decimal(str(a["contract_rate"])),
                        remaining_months=int(a["remaining_months"]), lender=a.get("lender_code", "generic"),
                        rate_type=a.get("rate_type", "fixed"),
                        comparison_posted_rate=None if a.get("comparison_posted_rate") is None else Decimal(str(a["comparison_posted_rate"])),
                        documented_discount=None if a.get("discount") is None else Decimal(str(a["discount"])))
    return _jsonable(calculate_penalty(inp).as_dict())


def t_renewal_shock(a: dict) -> dict:
    return renewal.renewal_shock(**a)


def t_offers(a: dict) -> dict:
    return renewal.offer_comparison(**a)


def t_switch(a: dict) -> dict:
    return renewal.switch_check(**a)


def t_home_value(a: dict) -> dict:
    return homevalue.indexed_value(**a)


def t_market(a: dict) -> dict:
    return ratebook.market_snapshot(a.get("on"))


def t_bank_rates(a: dict) -> dict:
    out = ratebook.bank_posted_table(a["bank"], a.get("on"))
    out["special"] = ratebook.bank_special_table(a["bank"], a.get("on"))["special"]
    return _jsonable(out)


def t_rate_change(a: dict) -> dict:
    return ratebook.rate_change(**a)


def t_lender_match(a: dict) -> dict:
    hits = lenders.match(province=a["province"].upper(), credit_score=int(a["credit_score"]), ltv=float(a["ltv"]),
                         gds=float(a["gds"]), tds=float(a["tds"]))
    by_cat: dict[str, list[str]] = {}
    for l in hits:
        by_cat.setdefault(l.category, []).append(l.name)
    return {"count": len(hits), "by_category": by_cat, "panel_verified": False,
            "note": "category-level illustrative policy; confirm with each lender"}


def t_lender_directory(a: dict) -> dict:
    return {"lenders": ratebook.find_lenders(a.get("query", ""), a.get("group"), int(a.get("limit", 10)))}


def t_guardrail(a: dict) -> dict:
    return guardrail.check(a["text"])


def t_screen(a: dict) -> dict:
    return kyc.screen(a["name"])


def t_penalty_methods(a: dict) -> dict:
    return {"methods": _jsonable(all_specs())}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("qualify_purchase", "OSFI B-20 stress test with GDS/TDS for a purchase. Returns qualifying rate, payments, ratios, LTV, pass/fail and reasons.",
         _obj(FILE_PROPS, FILE_REQ), t_qualify, "qualification"),
    Tool("insurance_premium", "Mortgage default insurance premium for a purchase (CMHC-style schedule), PST on premium and total loan.",
         _obj({"price": N, "down_payment": N, "amort_years": I, "province": S}, ["price", "down_payment"]), t_insurance, "insurance"),
    Tool("find_path_to_yes", "When a file fails qualification: compute every single-lever fix (max price, min down payment, debt payoff, min income, 30-year amortization), each re-verified by the stress test.",
         _obj(FILE_PROPS, FILE_REQ), t_remediate, "remediation"),
    Tool("max_purchase_price", "Highest purchase price that passes the stress test with the file's down payment.",
         _obj(FILE_PROPS, FILE_REQ), t_max_price, "remediation"),
    Tool("mortgage_payment", "Monthly payment (Canadian compounding) and optional balance after N payments.",
         _obj({"principal": N, "annual_rate": N, "amort_years": N, "variable": B, "months_paid": I},
              ["principal", "annual_rate", "amort_years"]), t_payment, "payments"),
    Tool("penalty_by_lender", "Prepayment penalty using the named lender's documented method and that lender's own posted-rate table from the rate book. Use for RBC, TD, Scotiabank, BMO, CIBC, National Bank or 'generic'. Dates are YYYY-MM-DD.",
         _obj({"lender": S, "balance": N, "contract_rate": N, "term_start": S, "maturity": S, "payout_date": S,
               "original_posted_rate": N, "contract_discount": N, "cashback": N, "discharge_fee": N,
               "rate_type": {"type": "string", "enum": ["fixed", "variable"]}, "rates_as_of": S},
              ["lender", "balance", "contract_rate", "term_start", "maturity"]), t_penalty_lender, "penalty"),
    Tool("penalty_quick", "Quick penalty estimate (greater of 3 months' interest and IRD) with an optional break-even refinance analysis.",
         _obj({"balance": N, "contract_rate": N, "months_remaining": N, "is_variable": B, "comparison_rate": N,
               "original_posted_rate": N, "current_posted_rate": N, "new_rate": N, "amort_years_remaining": N},
              ["balance", "contract_rate", "months_remaining"]), t_penalty_simple, "penalty"),
    Tool("renewal_payment_shock", "Payment before and after renewal for a mortgage taken out earlier at a lower rate.",
         _obj({"original_principal": N, "original_rate": N, "original_amort_years": N, "months_elapsed": I, "renewal_rate": N},
              ["original_principal", "original_rate", "original_amort_years", "months_elapsed", "renewal_rate"]), t_renewal_shock, "renewal"),
    Tool("compare_renewal_offers", "Compare renewal offers over the term: payment, interest, end balance and net cost after fees and cashback.",
         _obj({"balance": N, "remaining_amort_years": N, "term_years": N,
               "offers": {"type": "array", "items": _obj({"label": S, "rate": N, "fees": N, "cashback": N}, ["rate"])}},
              ["balance", "remaining_amort_years", "term_years", "offers"]), t_offers, "renewal"),
    Tool("switch_lender_check", "At renewal: would the borrower pass the stress test at another lender, and is the stress test required?",
         _obj({"balance": N, "remaining_amort_years": N, "new_rate": N, "annual_income": N, "property_tax_annual": N,
               "heat_annual": N, "condo_fees_monthly": N, "other_debt_monthly": N, "insured": B, "increases_amount_or_amort": B},
              ["balance", "remaining_amort_years", "new_rate", "annual_income"]), t_switch, "renewal"),
    Tool("home_value_estimate", "Indicative current value from purchase price, purchase year/month and postal code (not an appraisal).",
         _obj({"purchase_price": N, "purchase_year": I, "purchase_month": I, "postal_code": S, "renovation_spend": N},
              ["purchase_price", "purchase_year", "purchase_month", "postal_code"]), t_home_value, "collateral"),
    Tool("market_snapshot", "Bank of Canada policy rate, prime, GoC bond curve, Big-6 typical posted 5y and effective new-lending rates, with dates and sources.",
         _obj({"on": {"type": "string", "description": "YYYY-MM-DD, optional"}}), t_market, "market"),
    Tool("bank_rates", "A Big-6 bank's own posted and special rates by term from the rate book, with capture dates.",
         _obj({"bank": S, "on": S}, ["bank"]), t_bank_rates, "market"),
    Tool("rate_change", "Change in a rate series between two dates. series: policy_rate, prime, goc_bond_yield, big6_typical_posted, actual_rate_new_uninsured, actual_rate_new_insured.",
         _obj({"name": S, "term_months": I, "start": S, "end": S}, ["name", "start"]), t_rate_change, "market"),
    Tool("lender_match", "Lender categories whose (illustrative) policy fits the file's province, credit score, LTV, GDS and TDS.",
         _obj({"province": S, "credit_score": I, "ltv": N, "gds": N, "tds": N}, ["province", "credit_score", "ltv", "gds", "tds"]), t_lender_match, "lender"),
    Tool("lender_directory", "Search the Ontario lender directory (group: big6, bank, credit_union, monoline, online, private, trust, credit_co) with OSFI book sizes.",
         _obj({"query": S, "group": S, "limit": I}), t_lender_directory, "lender"),
    Tool("penalty_methods", "List the lender penalty methods the system models and whether each is verified.",
         _obj({}), t_penalty_methods, "penalty"),
    Tool("message_guardrail", "Check a borrower-facing message for rate quotes, approval promises, guarantees, pressure and requests for sensitive data.",
         _obj({"text": S}, ["text"]), t_guardrail, "compliance"),
    Tool("identity_screening", "Watch-list screening interface (returns NOT_SCREENED unless a licensed list is configured).",
         _obj({"name": S}, ["name"]), t_screen, "screening"),
]}


def specs(names: list[str] | None = None, extra: list[Tool] | None = None) -> list[dict]:
    pool = dict(TOOLS)
    for t in extra or []:
        pool[t.name] = t
    return [pool[n].spec() for n in (names or list(pool))]


def run(name: str, args: dict, extra: dict[str, Tool] | None = None) -> dict:
    pool = {**TOOLS, **(extra or {})}
    if name not in pool:
        return {"error": f"unknown tool {name!r}", "available": sorted(pool)}
    tool = pool[name]
    allowed = set(tool.parameters.get("properties", {}))
    clean = {k: v for k, v in (args or {}).items() if k in allowed and v is not None}
    missing = [k for k in tool.parameters.get("required", []) if k not in clean]
    if missing:
        return {"error": f"missing required arguments: {missing}"}
    try:
        return _jsonable(tool.fn(clean))
    except (ValueError, TypeError, KeyError, ArithmeticError) as e:
        return {"error": f"{type(e).__name__}: {e}"}


def dumps(x: Any) -> str:
    return json.dumps(_jsonable(x), separators=(",", ":"), default=str)

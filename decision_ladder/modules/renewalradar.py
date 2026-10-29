"""Renewal Radar inside the Mortgage OS.

Renewal Radar (modules/renewal-radar, the author's largest project) is registered as a module and its
engines are exposed to Nemotron as tools, imported in-process from ``modules/renewal-radar/backend``:

* rr_letter_xray            renewal letter / statement text -> fields with evidence, review packet, playbook
* rr_bank_penalty           lender-exact prepayment charge (16+ lender policies, many reproduced to the cent
                            against the lenders' own calculators) using the rate book's posted tables
* rr_penalty_helper         12 decision helpers: break-even, cheapest day, blend-and-extend, lump-sum first,
                            sensitivity, port vs break, countdown, stress test, net switch benefit, reverse
                            rate (discount implied by a quoted penalty), heatmap, plain-text summary
* rr_penalty_forecast       how the charge changes week by week until maturity
* rr_switch_pathway         dated OSFI / Finance Canada switch-vs-refinance pathway with sources
* rr_negotiation_script     retention call script, email and questions for a renewal negotiation
* rr_broker_book_review     a broker's whole book (CSV) -> opportunities, penalty floors, needs-data flags
* rr_wait_economics         switch now vs wait N months
* rr_lead_score             published renewal lead score (timing, savings, readiness)
* rr_renewal_plan           dated 120-day renewal checklist
* rr_penalty_accuracy       Renewal Radar's backtest report (oracle cases, exact-to-the-cent counts)

Nothing here fetches from the network: posted-rate tables come from the caller or from the OS rate book
(the same Renewal Radar rate-watch captures). Tools return errors as data; they never raise.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import date
from typing import Any

from ..agent.tools import B, I, N, S, Tool, _jsonable, _obj
from ..engines import ratebook
from .registry import MODULES_DIR, AppModule, add_module, add_tool

RR_DIR = MODULES_DIR / "renewal-radar"
BACKEND = RR_DIR / "backend"
_lock = threading.Lock()

add_module(AppModule(
    key="renewal-radar", name="Renewal Radar", stages=["servicing", "documents", "market"], kind="service",
    description="Renewal letter X-Ray, offer comparison, lender-exact penalties (reproduced against the lenders' own "
                "calculators), switch rules, negotiation scripts, broker book review, live rate watch and PDF reports.",
    directory="renewal-radar", web_root="frontend", repo="ALENZACODES/renewal-radar",
    live_url="https://renewal-radar-nplp.onrender.com",
    notes="FastAPI app; runs on its own port (RR_PORT, default 8100) because its frontend uses absolute paths. "
          "Start with: python -m decision_ladder.modules.rr_service"))


def _rr():
    """Put Renewal Radar's backend on sys.path (lazily) and return the package."""
    p = str(BACKEND)
    if p not in sys.path:
        sys.path.insert(0, p)
    import renewal  # noqa: F401
    return renewal


def _safe(fn):
    def run(a: dict) -> Any:
        try:
            _rr()
            return _jsonable(fn(a))
        except ImportError as e:
            return {"error": f"Renewal Radar dependency missing: {e}"}
        except Exception as e:  # noqa: BLE001 - tools report, never raise
            return {"error": f"{type(e).__name__}: {e}"}
    return run


def _d(s) -> date:
    return date.fromisoformat(str(s)[:10])


# ------------------------------------------------------------------------------------- letter X-Ray
def letter_xray(a: dict) -> dict:
    from renewal.ocr.contract_playbook import create_contract_playbook
    from renewal.ocr.fields import extract_ocr_fields
    pages = a.get("pages") or [a.get("text") or ""]
    if not any(str(p).strip() for p in pages):
        raise ValueError("text (or pages) required")
    ex = extract_ocr_fields(list(pages), filename=a.get("filename") or "letter.txt")
    pb = create_contract_playbook(list(pages), filename=a.get("filename") or "letter.txt")
    fields = {k: {"value": v.get("value"), "label": v.get("label"), "confidence": v.get("confidence_score"),
                  "page": v.get("page"), "evidence": v.get("excerpt"), "warnings": v.get("warnings") or []}
              for k, v in ex["fields"].items()}
    return {"fields": fields, "mortgage_draft": ex["mortgage_draft"], "missing_required": ex["missing_required"],
            "review_status": ex["review_status"], "warnings": ex["warnings"],
            "readiness": pb.get("readiness"),
            "tasks": [{"title": t.get("title"), "priority": t.get("priority"), "owner": t.get("owner")}
                      for t in pb.get("tasks", [])][:12],
            "notice": ex["notice"]}


# ------------------------------------------------------------------------------------- lender-exact penalty
_SID_BANK = {"P021": "RBC", "P023": "TD", "P025": "Scotiabank", "P027": "BMO", "P029": "CIBC", "P031": "National Bank"}


def _posted_table(lender: str, payout: date, supplied: dict | None) -> tuple[dict, str]:
    if supplied:
        return {int(k): float(v) for k, v in supplied.items()}, "supplied by caller"
    bank = ratebook.canonical_bank(lender)
    if not bank:
        raise ValueError(f"no rate-book posted table for {lender!r}: pass current_posted, e.g. {{\"24\": 5.29, \"36\": 5.89}}")
    t = ratebook.bank_posted_table(bank, payout.isoformat())
    if not t["posted"]:
        raise ValueError(f"no recorded {bank} posted rates on or before {payout}")
    dates = sorted({p["date"] for p in t["provenance"].values()})
    kinds = sorted({p["kind"] for p in t["provenance"].values()})
    return {int(k): float(v) for k, v in t["posted"].items()}, f"rate book ({bank}, captured {dates[0]}..{dates[-1]}, {'/'.join(kinds)})"


def _mortgage_and_policy(a: dict):
    from renewal.ratewatch.accuracy import policy_for
    from renewal.ratewatch.ird import Mortgage
    start = _d(a["start"])
    term = int(a.get("term_months") or 60)
    m = Mortgage(float(a["balance"]), float(a["contract_rate"]), term, start,
                 {term: float(a["posted_at_origination"])} if a.get("posted_at_origination") else {},
                 None if a.get("discount") is None else float(a["discount"]),
                 amort_months=int(a.get("amort_months") or 300),
                 maturity=_d(a["maturity"]) if a.get("maturity") else None,
                 original_amount=float(a["original_amount"]) if a.get("original_amount") else None)
    return m, policy_for(_policy_name(a["lender"]))


def _policy_name(lender: str) -> str:
    from renewal.ratewatch.ird import POLICIES
    low = lender.strip().lower()
    for name in POLICIES:
        if name.lower() == low:
            return name
    bank = ratebook.canonical_bank(lender)
    if bank:
        return bank
    for name in POLICIES:
        if name.lower().split()[0] in low:
            return name
    return lender


def bank_penalty(a: dict) -> dict:
    from renewal.ratewatch.ird import penalty
    m, pol = _mortgage_and_policy(a)
    payout = _d(a.get("payout") or date.today().isoformat())
    table, how = _posted_table(a["lender"], payout, a.get("current_posted"))
    res = penalty(m, pol, table, payout)
    return {**res, "lender_policy": pol.lender, "rates_source": how,
            "status": "exact-method" if pol.verified else "estimate", "method_source": pol.source or "category rule",
            "notice": "The lender's dated written payout statement is authoritative."}


HELPERS = ("break-even", "cheapest-day", "blend", "lump-sum", "sensitivity", "port-vs-break", "countdown",
           "stress-test", "net-switch", "reverse-rate", "heatmap", "summary")


def penalty_helper(a: dict) -> dict:
    from renewal.ratewatch import extras as x
    from renewal.ratewatch.ird import penalty
    tool = a["helper"]
    if tool not in HELPERS:
        raise ValueError(f"helper must be one of {HELPERS}")
    m, pol = _mortgage_and_policy(a)
    payout = _d(a.get("payout") or date.today().isoformat())
    needs_table = tool not in ("countdown", "stress-test", "reverse-rate")
    table, how = _posted_table(a["lender"], payout, a.get("current_posted")) if needs_table else ({}, "not needed")
    if tool in ("break-even", "blend", "net-switch") and a.get("new_rate") is None:
        raise ValueError("new_rate is required for this helper")
    if tool == "reverse-rate" and a.get("quoted_penalty") is None:
        raise ValueError("quoted_penalty is required for reverse-rate")
    nr, fees, ntm = a.get("new_rate"), float(a.get("fees") or 0), int(a.get("new_term_months") or 60)
    run = {
        "break-even": lambda: x.break_even(m, pol, table, payout, float(nr), fees, ntm),
        "cheapest-day": lambda: x.cheapest_day(m, pol, table, payout),
        "blend": lambda: x.blend_and_extend(m, payout, float(nr), ntm, pol, table),
        "lump-sum": lambda: x.lump_sum_first(m, pol, table, payout, float(a.get("allowance_pct") or 15.0),
                                             float(a["original_amount"]) if a.get("original_amount") else None),
        "sensitivity": lambda: x.sensitivity(m, pol, table, payout),
        "port-vs-break": lambda: x.port_vs_break(m, pol, table, payout, float(a.get("port_fee") or 0)),
        "countdown": lambda: x.renewal_countdown(m, payout),
        "stress-test": lambda: x.stress_test(float(a["balance"]), float(a["contract_rate"])),
        "net-switch": lambda: x.net_switch_benefit(m, pol, table, payout, float(nr), fees, new_term_months=ntm),
        "reverse-rate": lambda: x.reverse_rate(m, pol, payout, float(a["quoted_penalty"])),
        "heatmap": lambda: x.heatmap(m, pol, table, payout),
        "summary": lambda: {"text": x.summary_text(pol.lender, penalty(m, pol, table, payout),
                                                   x.cheapest_day(m, pol, table, payout), a.get("language") or "en")},
    }[tool]
    out = run()
    return {"helper": tool, "lender_policy": pol.lender, "rates_source": how, "result": out}


def penalty_forecast(a: dict) -> dict:
    from renewal.ratewatch.ird import forecast
    m, pol = _mortgage_and_policy(a)
    payout = _d(a.get("payout") or date.today().isoformat())
    table, how = _posted_table(a["lender"], payout, a.get("current_posted"))
    rows = forecast(m, pol, table, payout, step_days=int(a.get("step_days") or 7))
    return {"lender_policy": pol.lender, "rates_source": how, "transitions": [r for r in rows if r.get("transition")],
            "weeks": len(rows), "first": rows[0] if rows else None, "last": rows[-1] if rows else None}


# ------------------------------------------------------------------------------------- renewal decisions
MORTGAGE_FIELDS = {
    "balance": N, "offered_rate": N, "current_rate": N, "amortization_months": I, "term_months": I,
    "maturity_date": S, "frequency": S, "rate_type": S, "lender": S,
    "insurance_status": {"type": "string", "enum": ["insured", "uninsured", "unknown"]},
    "amortization_increase": B, "cash_out": N, "fees_financed": N, "current_ltv": N,
    "original_posted_rate": N, "original_contract_discount": N,
}


def _schema_mortgage(a: dict):
    from renewal.domain.schemas import Mortgage
    return Mortgage(**{k: v for k, v in a.items() if k in MORTGAGE_FIELDS and v is not None})


def switch_pathway(a: dict) -> dict:
    from renewal.domain.rules import switch_decision
    m = _schema_mortgage(a)
    return switch_decision(m, a.get("new_contract_rate"))


def negotiation_script(a: dict) -> dict:
    from renewal.domain.schemas import NegotiationRequest
    from renewal.services.negotiation import negotiation_packet
    req = NegotiationRequest(mortgage=_schema_mortgage(a), competing_rate=float(a["competing_rate"]),
                             competing_lender=a.get("competing_lender") or "a competing lender",
                             competitor_offer_verified=bool(a.get("competitor_offer_verified")),
                             goals=a.get("goals") or "lower_interest")
    return negotiation_packet(req)


def wait_economics(a: dict) -> dict:
    from renewal.broker.book_economics import wait_economics as we
    out = we(float(a["balance"]), float(a["old_rate"]), float(a["new_rate"]), int(a["amort_months"]),
             int(a["horizon_months"]), int(a["wait_months"]), float(a.get("later_penalty") or 0), float(a.get("fees") or 0))
    if out is None:
        raise ValueError("balance is fully repaid before the switch date")
    return out


def lead_score(a: dict) -> dict:
    from decimal import Decimal as D

    from renewal.leads.scoring import LeadFacts, score_lead
    f = LeadFacts(_d(a["renewal_date"]) if a.get("renewal_date") else None,
                  D(str(a["balance"])) if a.get("balance") is not None else None,
                  D(str(a["current_rate"])) if a.get("current_rate") is not None else None,
                  D(str(a["market_rate"])) if a.get("market_rate") is not None else None,
                  bool(a.get("has_statement")), bool(a.get("completed_analysis")))
    s = score_lead(f, _d(a.get("today") or date.today().isoformat()))
    return {"score": s.score, "band": s.band, "parts": s.parts,
            "note": "Uses renewal facts only, never personal attributes (Renewal Radar published score)."}


def renewal_plan(a: dict) -> dict:
    from renewal.services.plan import make_plan
    return {"maturity_date": a["maturity_date"], "steps": make_plan(a["maturity_date"])}


def penalty_accuracy(a: dict) -> dict:
    f = RR_DIR / "data" / "ratewatch" / "backtest_report.json"
    if not f.exists():
        raise ValueError("backtest report not found")
    from renewal.ratewatch.ird import POLICIES
    rep = json.loads(f.read_text())
    return {"report": rep, "verified_lender_methods": sorted(n for n, p in POLICIES.items() if p.verified),
            "category_rules": sorted(n for n, p in POLICIES.items() if not p.verified)}


# ------------------------------------------------------------------------------------- broker book
def book_review(a: dict) -> dict:
    from renewal.broker import book_review as br
    from renewal.broker.book_ingest import import_csv
    imp = import_csv(a["csv"])
    if not imp.get("deals"):
        raise ValueError("no deals could be read from the CSV")
    as_of = _d(a.get("as_of") or date.today().isoformat())
    if as_of >= date.today():  # keep the review offline: never touch the live rates board
        from datetime import timedelta
        as_of = date.today() - timedelta(days=1)

    def offline_rates(sids, day, fetch_live=True):
        out = {}
        for sid in sorted(s for s in sids if s):
            bank = _SID_BANK.get(sid)
            if bank:
                t = ratebook.bank_posted_table(bank, day.isoformat())
                if t["posted"]:
                    out[sid] = ({int(k): float(v) for k, v in t["posted"].items()}, f"OS rate book ({bank})")
                    continue
            out[sid] = ({}, "no recorded posted rates for this lender in the OS rate book")
        return out

    with _lock:  # temporary, local substitution of the network-backed rate loader
        orig = br.lender_rates
        br.lender_rates = offline_rates
        try:
            rev = br.review_book(imp["deals"], as_of=as_of, target_rate=a.get("target_rate"),
                                 new_term_months=int(a.get("new_term_months") or 60), fees=float(a.get("fees") or 0))
        finally:
            br.lender_rates = orig
    keep = ("deal_id", "borrower", "lender", "maturity_date", "contract_rate", "status", "recommendation",
            "net_benefit", "balance_today", "three_month_floor", "method_status", "days_to_maturity")
    return {"as_of": rev["as_of"], "deals_reviewed": rev["deals_reviewed"], "summary": rev["summary"],
            "total_net_benefit": rev["total_net_benefit"], "best_offer": rev["best_offer"],
            "import": {"rows": imp.get("rows"), "with_issues": imp.get("with_issues"), "mapping": imp.get("mapping")},
            "results": [{k: r.get(k) for k in keep} for r in rev["results"]]}


# ------------------------------------------------------------------------------------- registration
PENALTY_PROPS = {
    "lender": {"type": "string", "description": "e.g. RBC, TD, Scotiabank, BMO, CIBC, National Bank, Tangerine, Simplii, "
                                                "Desjardins, ATB, Laurentian, Equitable Bank, Bridgewater, Haventree, First National, MCAP"},
    "balance": N, "contract_rate": N, "term_months": I,
    "start": {"type": "string", "description": "term start YYYY-MM-DD"},
    "maturity": {"type": "string", "description": "YYYY-MM-DD (optional; start + term if omitted)"},
    "payout": {"type": "string", "description": "payout date YYYY-MM-DD (default today)"},
    "discount": {"type": "number", "description": "discount off posted at origination, percentage points"},
    "posted_at_origination": {"type": "number", "description": "lender's posted rate for the term on the start date"},
    "amort_months": I, "original_amount": N,
    "current_posted": {"type": "object", "description": "optional {term_months: posted rate} override"},
}
PEN_REQ = ["lender", "balance", "contract_rate", "start"]

for tool in [
    Tool("rr_letter_xray", "Renewal Radar Letter X-Ray: read a renewal letter or mortgage statement (text) into fields "
         "with evidence (balance, current and offered rate, term, maturity, amortization, frequency), a review status and a "
         "review playbook. Use when the broker pastes a lender letter.",
         _obj({"text": S, "pages": {"type": "array", "items": S}, "filename": S}), _safe(letter_xray), "documents"),
    Tool("rr_bank_penalty", "Renewal Radar lender-exact prepayment charge for a closed fixed mortgage, using that lender's "
         "documented method (RBC, TD, Scotiabank, BMO, CIBC, National Bank and others reproduced against the lenders' own "
         "calculators) and the rate book's captured posted rates. Needs the discount or posted_at_origination for IRD.",
         _obj(PENALTY_PROPS, PEN_REQ), _safe(bank_penalty), "penalty"),
    Tool("rr_penalty_helper", "Renewal Radar decision helpers on a fixed mortgage: helper = break-even | cheapest-day | blend | "
         "lump-sum | sensitivity | port-vs-break | countdown | stress-test | net-switch | reverse-rate (discount implied by a "
         "lender's quoted penalty) | heatmap | summary.",
         _obj({**PENALTY_PROPS, "helper": {"type": "string", "enum": list(HELPERS)}, "new_rate": N, "fees": N,
               "new_term_months": I, "allowance_pct": N, "quoted_penalty": N, "port_fee": N, "language": S},
              PEN_REQ + ["helper"]), _safe(penalty_helper), "penalty"),
    Tool("rr_penalty_forecast", "How a fixed mortgage's prepayment charge changes week by week until maturity "
         "(Renewal Radar), with the dates where the comparison term changes.",
         _obj({**PENALTY_PROPS, "step_days": I}, PEN_REQ), _safe(penalty_forecast), "penalty"),
    Tool("rr_switch_pathway", "Renewal Radar switch pathway: is moving lenders at renewal a straight switch (no stress test "
         "under OSFI's Nov 2024 exemption / insured switch rules) or new underwriting? Returns status, qualifying rate, reasons, sources.",
         _obj({**MORTGAGE_FIELDS, "new_contract_rate": N}, ["balance", "offered_rate", "maturity_date"]),
         _safe(switch_pathway), "renewal"),
    Tool("rr_negotiation_script", "Renewal Radar negotiation packet for the current lender's retention team: call script, "
         "email, questions and the modelled payment difference against a competing rate.",
         _obj({**MORTGAGE_FIELDS, "competing_rate": N, "competing_lender": S, "competitor_offer_verified": B,
               "goals": {"type": "string", "enum": ["lower_payment", "lower_interest", "flexibility"]}},
              ["balance", "offered_rate", "maturity_date", "competing_rate"]), _safe(negotiation_script), "renewal"),
    Tool("rr_wait_economics", "Switch now vs wait N months (Renewal Radar): interest compared over a common horizon, "
         "including the later penalty and fees.",
         _obj({"balance": N, "old_rate": N, "new_rate": N, "amort_months": I, "horizon_months": I, "wait_months": I,
               "later_penalty": N, "fees": N}, ["balance", "old_rate", "new_rate", "amort_months", "horizon_months", "wait_months"]),
         _safe(wait_economics), "renewal"),
    Tool("rr_lead_score", "Renewal Radar's published renewal lead score (0-100, hot/warm/nurture) from renewal timing, "
         "potential savings and readiness. Never uses personal attributes.",
         _obj({"renewal_date": S, "balance": N, "current_rate": N, "market_rate": N, "has_statement": B,
               "completed_analysis": B, "today": S}), _safe(lead_score), "lead"),
    Tool("rr_renewal_plan", "Dated renewal checklist from 120 days before maturity to maturity day (Renewal Radar).",
         _obj({"maturity_date": S}, ["maturity_date"]), _safe(renewal_plan), "renewal"),
    Tool("rr_broker_book_review", "Renewal Radar broker book review: a CSV export of a broker's funded deals -> per-deal "
         "status (strong/possible/renewal_window/needs_data/no_opportunity), penalty floors, net benefit vs a target rate.",
         _obj({"csv": S, "as_of": S, "target_rate": N, "new_term_months": I, "fees": N}, ["csv"]),
         _safe(book_review), "renewal"),
    Tool("rr_penalty_accuracy", "Renewal Radar's penalty accuracy evidence: backtest report against lender calculators and "
         "which lender methods are verified vs category rules.", _obj({}), _safe(penalty_accuracy), "penalty"),
]:
    add_tool(tool, "renewal-radar")

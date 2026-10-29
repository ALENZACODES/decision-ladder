"""FINTRAC identification and record-keeping check for a mortgage broker's file (PCMLTFA, mortgage sector in
force 2024-10-11).

Identity methods for persons follow FINTRAC's "Methods to verify the identity of persons and entities":
government-issued photo ID (authentic, valid and current; record name, date, type, number, jurisdiction and
country, expiry), credit file (Canadian bureau, at least 3 years old, searched at the time of verification;
record name, date, bureau, file number), dual-process (two different reliable sources, not the client or the
broker, covering two of: name+address, name+DOB, name+financial account), and reliance on another reporting
entity or an agent (written agreement). Entity verification methods are not evaluated beyond presence.

Transactions: large cash or virtual currency of $10,000 or more (24-hour rule) needs a report, identity and a
third-party determination; every amount received needs a receipt-of-funds record; $100,000+ in cash or virtual
currency triggers a PEP/HIO determination. Records are kept at least five years.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .calendar import _d, add_years
from .sources import cite, envelope

LARGE = 10_000
PEP_TRIGGER = 100_000
INFO_TYPES = {"name_address", "name_dob", "name_account"}
PHOTO_FIELDS = ("doc_type", "doc_number", "jurisdiction", "country")
PERSON_RECORD = ("address", "dob", "occupation")


def _person_id(c: dict) -> list[str]:
    m, vd = c.get("method"), c.get("verified_date")
    gaps = [] if vd else ["verified_date"]
    if m == "photo_id":
        p = c.get("photo_id") or {}
        gaps += [f"photo_id.{k}" for k in PHOTO_FIELDS if not p.get(k)]
        if not p.get("authenticated"):
            gaps.append("photo_id.authenticated (document authenticity not confirmed)")
        if not p.get("photo_matched"):
            gaps.append("photo_id.photo_matched (name and photo not matched to the person)")
        if p.get("expiry_date") and vd and _d(p["expiry_date"]) < _d(vd):
            gaps.append("photo_id expired before verification (must be valid and current)")
    elif m == "credit_file":
        cf = c.get("credit_file") or {}
        gaps += [f"credit_file.{k}" for k in ("bureau", "reference_number") if not cf.get(k)]
        if float(cf.get("history_years") or 0) < 3:
            gaps.append("credit_file.history_years must be at least 3")
        if cf.get("client_provided") or not cf.get("searched_at_verification"):
            gaps.append("credit file must be searched at the time of verification, not a prior or client copy")
    elif m == "dual_process":
        src = (c.get("dual_process") or {}).get("sources") or []
        names = {s.get("name") for s in src if s.get("name")}
        kinds = {s.get("info") for s in src if s.get("info") in INFO_TYPES}
        if len(src) < 2 or len(names) < 2:
            gaps.append("dual_process needs two different reliable sources")
        if len(kinds) < 2:
            gaps.append("dual_process needs two different kinds of information (name+address, name+DOB, "
                        "name+account)")
        if any(s.get("is_client_or_broker") for s in src):
            gaps.append("dual_process source cannot be the client or the brokerage")
        gaps += [f"dual_process.sources[{i}].reference" for i, s in enumerate(src) if not s.get("reference")]
    elif m in ("reliance", "agent"):
        r = c.get(m) or {}
        if not r.get("written_agreement"):
            gaps.append(f"{m}: written agreement required before relying on it")
        if not r.get("records_obtained"):
            gaps.append(f"{m}: identification information obtained from the other party")
    elif m == "previously_verified":
        if not c.get("prior_records_kept"):
            gaps.append("previously_verified: earlier verification records must be on file")
    else:
        gaps.append("method (photo_id, credit_file, dual_process, reliance, agent or previously_verified)")
    return gaps


def _client(c: dict) -> dict:
    is_entity = c.get("type") == "entity"
    gaps = [] if c.get("name") else ["name"]
    if is_entity:
        gaps += [] if c.get("method") and c.get("verified_date") else ["entity identity method and verified_date"]
        gaps += [] if c.get("address") else ["address"]
        gaps += [] if c.get("nature_of_business") else ["nature_of_business"]
        if "beneficial_owners" not in c:
            gaps.append("beneficial_owners (individuals owning or controlling 25% or more; empty list if none)")
        else:
            bad = [o.get("name") for o in c["beneficial_owners"] if float(o.get("pct", 0)) < 25]
            if bad:
                gaps.append(f"beneficial_owners below 25% listed as owners: {bad}")
    else:
        gaps += _person_id(c)
        gaps += [k for k in PERSON_RECORD if not c.get(k)]
    if not c.get("third_party_determined"):
        gaps.append("third_party_determined")
    elif c.get("third_party"):
        tp = c["third_party"]
        gaps += [f"third_party.{k}" for k in ("name", "relationship") if not tp.get(k)]
    if not c.get("pep_hio_determined"):
        gaps.append("pep_hio_determined")
    elif c.get("pep_hio") and c.get("high_risk_date"):
        due = _d(c["high_risk_date"]) + timedelta(days=30)
        if not c.get("source_of_wealth_date") or _d(c["source_of_wealth_date"]) > due:
            gaps.append(f"source of wealth for high-risk PEP/HIO due by {due.isoformat()}")
    return {"name": c.get("name"), "type": "entity" if is_entity else "person", "missing": gaps, "ok": not gaps}


def _when(t: dict) -> datetime:
    s = str(t.get("datetime") or t.get("date"))
    return datetime.fromisoformat(s if "T" in s or " " in s else s + "T00:00:00")


def _transactions(txs: list[dict]) -> list[dict]:
    out = []
    reportable = [t for t in txs if (t.get("cash") or t.get("virtual_currency")) and not t.get("from_financial_entity")]
    for t in txs:
        issues = []
        if not t.get("receipt_of_funds_record"):
            issues.append("receipt of funds record")
        payer_entity = t.get("payer_type") == "entity"
        if not t.get("payer_verified"):
            issues.append("payer identity (entity: within 30 days)" if payer_entity else "payer identity at the time")
        if t in reportable:
            when = _when(t)
            window = [x for x in reportable if x.get("payer") == t.get("payer")
                      and timedelta(0) <= when - _when(x) < timedelta(hours=24)]
            total = sum(float(x["amount"]) for x in window)
            if total >= LARGE and not t.get("report_filed"):
                kind = "virtual currency" if t.get("virtual_currency") else "cash"
                issues.append(f"large {kind} report ({total:,.2f} within 24 hours)")
            if total >= LARGE and not t.get("third_party_determined"):
                issues.append("third-party determination for the large transaction")
            if total >= PEP_TRIGGER and not t.get("pep_hio_determined"):
                issues.append("PEP/HIO determination ($100,000+ in cash or virtual currency)")
        out.append({"date": str(t.get("datetime") or t.get("date")), "amount": float(t["amount"]),
                    "payer": t.get("payer"), "missing": issues, "ok": not issues})
    return out


PROGRAM = ("compliance_officer", "policies", "risk_assessment", "training")


def check(a: dict) -> dict:
    clients = [_client(c) for c in a.get("clients") or []]
    if not clients:
        raise ValueError("at least one client is required")
    txs = _transactions(a.get("transactions") or [])
    out = {"clients": clients, "transactions": txs}
    if a.get("program") is not None:
        p = a["program"]
        gaps = [k for k in PROGRAM if not p.get(k)]
        as_of = _d(a.get("as_of") or datetime.now().date())
        last = p.get("effectiveness_review_date")
        if not last or add_years(_d(last), 2) < as_of:
            gaps.append("effectiveness review within the last two years")
        out["program"] = {"missing": gaps, "ok": not gaps}
    if a.get("record_date"):
        out["retain_until"] = add_years(_d(a["record_date"]), 5).isoformat()
    out["missing"] = ([f"{c['name']}: {m}" for c in clients for m in c["missing"]]
                      + [f"{t['date']} {t['amount']:,.2f}: {m}" for t in txs for m in t["missing"]]
                      + [f"program: {m}" for m in out.get("program", {}).get("missing", [])])
    out["complete"] = not out["missing"]
    cites = [cite("FINTRAC_METHODS", "persons"), cite("FINTRAC_MORTGAGE", "when to verify; information record")]
    cites.append(cite("PCMLTFA_MORTGAGE_2024", "PEP/HIO, third party, retention, compliance program"))
    return envelope(out, "disclosure.fintrac", cites)

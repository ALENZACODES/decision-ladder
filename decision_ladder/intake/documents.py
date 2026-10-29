"""Document reading for the Documents rung: pay stubs, T4 slips, Notices of Assessment, employment
letters, renewal letters and mortgage statements, pasted as text (or text from a PDF/OCR step).

Two passes, like client-email intake:

1. A deterministic reader classifies the document by its wording and pulls the figures underwriting cares
   about, each with the exact line it came from.
2. Optionally Nemotron Nano reads the same text in JSON mode. A model figure is kept only if the quote it
   gives is in the document; disagreements with the deterministic reader are flagged.

The output plugs straight into the file as ``documents: [{type, extracted, quotes, ...}]``, which the
Documents rung reconciles against the stated figures.
"""
from __future__ import annotations

import re
from typing import Any

from ..llm.client import LLMError, NemotronClient
from .extract import _close, _money, _norm_quote

DOC_TYPES = {
    "t4": (r"\bT4\b", r"statement of remuneration", r"box 14|employment income"),
    "noa": (r"notice of (re)?assessment", r"line 15000|total income", r"canada revenue agency"),
    "pay_stub": (r"pay (period|date|stub|statement)|earnings statement", r"gross pay|gross earnings", r"\bYTD\b|year[- ]to[- ]date"),
    "employment_letter": (r"to whom it may concern|employment (verification|confirmation)", r"annual (base )?salary|salary of", r"employed (with|by|at)|has been employed"),
    "renewal_letter": (r"renewal", r"maturity date|matures on|renewal date", r"offer|options"),
    "mortgage_statement": (r"mortgage statement|annual statement", r"principal balance|outstanding balance|balance", r"interest rate"),
}

PERIODS = {"weekly": 52, "bi-weekly": 26, "biweekly": 26, "semi-monthly": 24, "semimonthly": 24, "monthly": 12}
_AMT = r"\$?\s?\d[\d,]*(?:\.\d{2})?"
_MONTHS = ("january february march april may june july august september october november december").split()


def classify(text: str) -> tuple[str, float]:
    low = (text or "").lower()
    best, score = "unknown", 0.0
    for kind, pats in DOC_TYPES.items():
        hits = sum(1 for p in pats if re.search(p, low, re.I))
        s = hits / len(pats)
        if s > score:
            best, score = kind, s
    return (best, round(score, 2)) if score >= 0.34 else ("unknown", round(score, 2))


def _date(s: str) -> str | None:
    s = s.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m:
        mon = next((i + 1 for i, n in enumerate(_MONTHS) if n.startswith(m.group(1).lower()[:3])), None)
        if mon:
            return f"{m.group(3)}-{mon:02d}-{int(m.group(2)):02d}"
    return None


def read(text: str) -> dict:
    """Deterministic read. Returns {type, confidence, extracted, quotes, notes}."""
    t = text or ""
    kind, conf = classify(t)
    ex: dict[str, Any] = {}
    quotes: dict[str, str] = {}
    notes: list[str] = []

    def put(k: str, v: Any, q: str) -> None:
        if v is not None and k not in ex:
            ex[k], quotes[k] = v, q.strip()

    def first(rx: str):
        return re.search(rx, t, re.I | re.M)

    if kind == "t4":
        m = first(rf"(?:box\s*14|employment income)[^\d$\n]{{0,40}}({_AMT})")
        if m:
            put("annual_income", _money(m.group(1)), m.group(0))
        m = first(r"\b(20\d{2})\b")
        if m:
            put("tax_year", int(m.group(1)), m.group(0))
    elif kind == "noa":
        m = first(rf"(?:line\s*15000|total income)[^\d$\n]{{0,40}}({_AMT})")
        if m:
            put("annual_income", _money(m.group(1)), m.group(0))
        m = first(rf"(?:balance (?:owing|owed)|amount owing)[^\d$\n]{{0,30}}({_AMT})")
        if m and (_money(m.group(1)) or 0) > 0:
            notes.append(f"CRA balance owing {m.group(1).strip()}: confirm it is paid before closing.")
            put("cra_balance_owing", _money(m.group(1)), m.group(0))
    elif kind == "pay_stub":
        freq = next((f for f in PERIODS if re.search(rf"\b{f}\b", t, re.I)), None)
        m = first(rf"(?:annual(?:ized)? (?:salary|rate))[^\d$\n]{{0,30}}({_AMT})")
        if m:
            put("annual_income", _money(m.group(1)), m.group(0))
        m = first(rf"gross (?:pay|earnings)(?! *ytd)[^\d$\n]{{0,30}}({_AMT})")
        if m:
            put("gross_per_period", _money(m.group(1)), m.group(0))
            if freq and "annual_income" not in ex:
                put("annual_income", round(_money(m.group(1)) * PERIODS[freq], 2), m.group(0))
                notes.append(f"Annualized: {m.group(1).strip()} x {PERIODS[freq]} ({freq}) pay periods.")
        if freq:
            put("pay_frequency", freq, freq)
        m = first(rf"(?:YTD|year[- ]to[- ]date)[^\d$\n]{{0,30}}({_AMT})")
        if m:
            put("ytd_gross", _money(m.group(1)), m.group(0))
    elif kind == "employment_letter":
        m = first(rf"(?:annual (?:base )?salary|salary of|base salary)[^\d$\n]{{0,30}}({_AMT})")
        if m:
            put("annual_income", _money(m.group(1)), m.group(0))
        m = first(r"(?:since|employed (?:with \w+ )?since|start date[:\s]*)\s*([A-Za-z]+\.?\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})")
        if m:
            put("employment_start", _date(m.group(1)), m.group(0))
        if re.search(r"\b(probation|contract|temporary|part[- ]time)\b", t, re.I):
            notes.append("Letter mentions probation/contract/temporary/part-time: check lender policy.")
        put("permanent", bool(re.search(r"\bpermanent\b", t, re.I)) or None, "permanent")
    elif kind in ("renewal_letter", "mortgage_statement"):
        m = first(rf"(?:principal|outstanding|mortgage)? ?balance[^\d$\n]{{0,40}}({_AMT})")
        if m:
            put("balance", _money(m.group(1)), m.group(0))
        m = first(r"(?:current|existing|your) (?:interest )?rate[^\d\n]{0,25}(\d{1,2}\.\d{1,3})\s?%") or \
            first(r"interest rate[^\d\n]{0,25}(\d{1,2}\.\d{1,3})\s?%")
        if m:
            put("contract_rate", float(m.group(1)), m.group(0))
        m = first(r"(?:maturity date|matures on|renewal date)[:\s]*([A-Za-z]+\.?\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})")
        if m:
            put("maturity", _date(m.group(1)), m.group(0))
        offers = [(float(r), q) for q, r in ((mm.group(0), mm.group(1)) for mm in
                  re.finditer(r"(?:\d[- ]year|\d+ year)[^%\n]{0,40}?(\d{1,2}\.\d{1,3})\s?%", t, re.I))]
        if offers and kind == "renewal_letter":
            put("renewal_offers", [o[0] for o in offers], "; ".join(o[1] for o in offers))
            five = [o for o in offers if re.search(r"\b5[- ]year", o[1], re.I)]
            put("renewal_rate", (five or offers)[0][0], (five or offers)[0][1])
        m = first(r"\b(RBC|Royal Bank|TD|Scotiabank|BMO|CIBC|National Bank|First National|MCAP|Equitable|Meridian|Desjardins)\b")
        if m:
            put("lender", m.group(1), m.group(0))
    return {"type": kind, "confidence": conf, "extracted": ex, "quotes": quotes, "notes": notes}


DOC_SYSTEM = ("You read Canadian mortgage underwriting documents (T4, Notice of Assessment, pay stub, employment letter, "
              "renewal letter, mortgage statement). Return JSON {\"type\": one of t4|noa|pay_stub|employment_letter|"
              "renewal_letter|mortgage_statement|unknown, \"fields\": {name: {\"value\": ..., \"quote\": \"exact text\"}}}. "
              "Field names: annual_income (dollars/year; annualize pay stubs only if the pay frequency is stated), balance, "
              "contract_rate (percent), renewal_rate (percent, 5-year if offered), maturity (YYYY-MM-DD), lender, employment_start "
              "(YYYY-MM-DD). Only include values the document states; the quote must be copied exactly.")
NUMERIC = {"annual_income", "balance", "contract_rate", "renewal_rate"}


def read_document(text: str, llm: NemotronClient | None = None) -> dict:
    out = read(text)
    out["model"] = None
    if llm is None:
        return out
    try:
        raw = llm.json(DOC_SYSTEM, text[:8000], purpose="document-read")
    except LLMError as e:
        out["model"] = {"error": str(e)}
        return out
    src = _norm_quote(text)
    agree, conflicts, dropped, added = [], [], [], []
    for name, item in (raw.get("fields") or {}).items():
        if not isinstance(item, dict) or name not in ("annual_income", "balance", "contract_rate", "renewal_rate",
                                                      "maturity", "lender", "employment_start"):
            continue
        q, v = str(item.get("quote") or ""), item.get("value")
        if not q or _norm_quote(q) not in src:
            dropped.append(name)
            continue
        if name in NUMERIC:
            v = _money(str(v)) if isinstance(v, str) else (float(v) if v is not None else None)
        if v is None:
            continue
        if name in out["extracted"]:
            (agree if _close(out["extracted"][name], v) else conflicts).append(
                name if _close(out["extracted"][name], v) else {"field": name, "reader": out["extracted"][name], "model": v, "quote": q})
        else:
            out["extracted"][name], out["quotes"][name] = v, q
            added.append(name)
    mt = raw.get("type")
    out["model"] = {"type": mt, "agree": agree, "conflicts": conflicts, "dropped": dropped, "added": added}
    if out["type"] == "unknown" and mt in DOC_TYPES:
        out["type"] = mt
    return out

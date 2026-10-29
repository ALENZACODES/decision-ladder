"""Free text in, structured mortgage file out.

Brokers receive files as emails ("hi, we found a place in Oakville for 1.1M, we have 220k saved...") and
as documents (renewal letters, pay stubs, mortgage statements). Two extractors run on the same text:

* a deterministic pattern extractor (fast, predictable, misses a lot), and
* Nemotron Nano in JSON mode, which must quote the exact text span for every value it returns.

The two are reconciled field by field. A model value whose quoted span is not in the source text is
dropped (no evidence, no field). Where both extractors found a value and they disagree, the field is
flagged for the broker instead of silently picking one.
"""
from __future__ import annotations

import re
from typing import Any

from ..llm.client import LLMError, NemotronClient

FIELDS = {
    "borrower_name": "string", "purpose": "purchase|renewal|refinance", "province": "two-letter code",
    "postal_code": "string", "price": "number (dollars)", "down_payment": "number (dollars)",
    "annual_income": "number (dollars per year, household gross)", "credit_score": "integer",
    "contract_rate": "number (percent)", "amort_years": "integer", "property_tax_annual": "number",
    "condo_fees_monthly": "number", "other_debt_monthly": "number", "first_time_buyer": "boolean",
    "new_build": "boolean", "balance": "number (mortgage balance)", "maturity": "YYYY-MM-DD",
    "term_start": "YYYY-MM-DD", "renewal_rate": "number (percent)", "lender": "string",
    "savings": "number (dollars saved / liquid assets available for closing)", "city": "string",
    "property_type": "detached|semi|town|condo", "co_borrower": "boolean",
}

EXTRACT_SYSTEM = (
    "Extract mortgage application fields from the text. Return JSON: {\"fields\": {name: {\"value\": ..., "
    "\"quote\": \"exact words from the text that state it\"}}}. Only include fields that the text states. "
    "Convert '1.1M' to 1100000 and '220k' to 220000. Percent values as numbers (4.29 for 4.29%). "
    "Allowed fields and types: " + ", ".join(f"{k} ({v})" for k, v in FIELDS.items()) +
    ". Never guess; omit anything not stated.")

PROVINCES = {"ontario": "ON", "alberta": "AB", "british columbia": "BC", "quebec": "QC", "manitoba": "MB",
             "saskatchewan": "SK", "nova scotia": "NS", "new brunswick": "NB", "newfoundland": "NL", "pei": "PE"}
ON_CITIES = ("toronto", "oakville", "mississauga", "brampton", "markham", "richmond hill", "vaughan", "ottawa",
             "hamilton", "burlington", "london", "kitchener", "waterloo", "oshawa", "barrie", "guelph")


def _money(s: str) -> float | None:
    s = s.strip().lower().replace("$", "").replace(",", "").replace(" ", "")
    mult = 1.0
    if s.endswith(("m", "mm")):
        mult, s = 1_000_000.0, s.rstrip("m")
    elif s.endswith("k"):
        mult, s = 1_000.0, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return None


_M = r"\$?\s?\d[\d,]*(?:\.\d+)?\s?(?:k|m|mm)?\b"
F = r"(?:\s*(?:of|is|are|was|:|about|around|roughly|approximately|approx\.?))*"


def pattern_extract(text: str) -> dict[str, dict]:
    t = text or ""
    low = t.lower()
    out: dict[str, dict] = {}

    def put(name: str, value: Any, quote: str) -> None:
        if value is not None and name not in out:
            out[name] = {"value": value, "quote": quote.strip()}

    for rx, name in ((rf"(?:price|listed at|offer(?:ed)? (?:of|at)|purchase (?:price )?(?:of|at)|for)\s+({_M})", "price"),
                     (rf"(?:down payment|savings){F}\s*({_M})", "down_payment"),
                     (rf"({_M})\s*(?:saved|in savings|(?:for the )?down payment|down\b)", "down_payment"),
                     (rf"(?:income|earn(?:s|ing)?|make|salary){F}\s*({_M})", "annual_income"),
                     (rf"(?:balance|owe|outstanding){F}\s*({_M})", "balance"),
                     (rf"(?:car|loan|debt|payments?)\s*(?:of|is|:)?\s*({_M})\s*(?:/|a|per)\s*(?:mo|month)", "other_debt_monthly"),
                     (rf"(?:property tax(?:es)?){F}\s*({_M})", "property_tax_annual"),
                     (rf"(?:condo|maintenance) fees?\s*(?:of|is|:)?\s*({_M})", "condo_fees_monthly")):
        m = re.search(rx, t, re.I)
        if m:
            put(name, _money(m.group(1)), m.group(0))
    for rx in (rf"({_M})\s*(?:saved|in savings)", rf"(?:savings of|saved up|have saved|we've saved)\s*({_M})"):
        m = re.search(rx, t, re.I)
        if m:
            put("savings", _money(m.group(1)), m.group(0))
            break
    m = re.search(r"\b(semi(?:-detached)?|detached|town ?house|townhome|condo(?:minium)?)\b", t, re.I)
    if m:
        w = m.group(1).lower()
        put("property_type", "semi" if w.startswith("semi") else "town" if w.startswith("town") else
            "condo" if w.startswith("condo") else "detached", m.group(0))
    m = re.search(r"\b(combined income|our income|my (?:wife|husband|partner|spouse)|co-?borrower|co-?signer)\b", t, re.I)
    if m:
        put("co_borrower", True, m.group(0))
    m = re.search(r"(?:credit score|beacon|score)\s*(?:of|is|:|around|about)?\s*(\d{3})", t, re.I)
    if m:
        put("credit_score", int(m.group(1)), m.group(0))
    m = re.search(r"(\d{1,2}(?:\.\d{1,3})?)\s?%\s*(?:[\w-]+\s){0,4}?(?:rate|fixed|variable)", t, re.I) or \
        re.search(r"(?:rate|at)\s*(?:of|is|:)?\s*(\d{1,2}(?:\.\d{1,3})?)\s?%", t, re.I)
    if m:
        put("renewal_rate" if "renew" in low and "offer" in low else "contract_rate", float(m.group(1)), m.group(0))
    m = re.search(r"(\d{2})[- ]?(?:year|yr)s?\s+amort", t, re.I)
    if m:
        put("amort_years", int(m.group(1)), m.group(0))
    m = re.search(r"\b([ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z])\s?(\d[ABCEGHJ-NPRSTV-Z]\d)\b", t)
    if m:
        put("postal_code", f"{m.group(1)} {m.group(2)}".upper(), m.group(0))
    for nm, code in PROVINCES.items():
        if nm in low:
            put("province", code, nm)
            break
    else:
        for c in ON_CITIES:
            if c in low:
                put("province", "ON", c)
                break
    for c in ON_CITIES:
        if re.search(rf"\b{c}\b", low):
            put("city", c.title(), c)
            break
    if re.search(r"first[- ]time (?:home ?)?buyer", t, re.I):
        put("first_time_buyer", True, re.search(r"first[- ]time (?:home ?)?buyer", t, re.I).group(0))
    if re.search(r"\b(?:new build|pre-?construction|brand new)\b", t, re.I):
        put("new_build", True, re.search(r"\b(?:new build|pre-?construction|brand new)\b", t, re.I).group(0))
    if re.search(r"\brenew", t, re.I):
        put("purpose", "renewal", re.search(r"\brenew\w*", t, re.I).group(0))
    elif re.search(r"\brefinanc", t, re.I):
        put("purpose", "refinance", re.search(r"\brefinanc\w*", t, re.I).group(0))
    elif "price" in out:
        put("purpose", "purchase", out["price"]["quote"])
    m = re.search(r"\b(?:my name is|i am|i'm|this is)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)", t)
    if m:
        put("borrower_name", m.group(1), m.group(0))
    else:
        m = re.search(r"\n\s*(?:thanks|regards|cheers|best)[,!]?\s*\n\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)", t, re.I)
        if m:
            put("borrower_name", m.group(1), m.group(0))
    return out


def _norm_quote(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _coerce(name: str, v: Any) -> Any:
    kind = FIELDS.get(name, "")
    if v is None:
        return None
    if kind.startswith("number"):
        if isinstance(v, str):
            return _money(v)
        return float(v)
    if kind == "integer":
        return int(float(v))
    if kind == "boolean":
        return v if isinstance(v, bool) else str(v).lower() in ("true", "yes", "1")
    if name == "province":
        s = str(v).strip()
        return PROVINCES.get(s.lower(), s.upper()[:2])
    if name == "purpose":
        s = str(v).lower()
        return s if s in ("purchase", "renewal", "refinance") else None
    return str(v).strip()


def model_extract(llm: NemotronClient, text: str) -> dict[str, dict]:
    raw = llm.json(EXTRACT_SYSTEM, text[:8000], purpose="intake-extract")
    fields = raw.get("fields", raw) if isinstance(raw, dict) else {}
    src = _norm_quote(text)
    out = {}
    for name, item in (fields or {}).items():
        if name not in FIELDS:
            continue
        if not isinstance(item, dict):
            item = {"value": item, "quote": ""}
        quote = str(item.get("quote") or "")
        try:
            val = _coerce(name, item.get("value"))
        except (TypeError, ValueError):
            continue
        if val is None:
            continue
        grounded = bool(quote) and _norm_quote(quote) in src
        out[name] = {"value": val, "quote": quote, "grounded": grounded}
    return out


def _close(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(float(a) - float(b)) <= max(0.005 * max(abs(float(a)), abs(float(b))), 0.01)
    return str(a).strip().lower() == str(b).strip().lower()


def reconcile(pattern: dict[str, dict], model: dict[str, dict]) -> dict:
    fields, conflicts, dropped = {}, [], []
    for name in sorted(set(pattern) | set(model)):
        p, m = pattern.get(name), model.get(name)
        if m and not m.get("grounded"):
            dropped.append({"field": name, "value": m["value"], "quote": m.get("quote"),
                            "reason": "model quote not found in source text"})
            m = None
        if p and m:
            if _close(p["value"], m["value"]):
                fields[name] = {"value": m["value"], "source": "both", "quote": m["quote"]}
            else:
                conflicts.append({"field": name, "pattern": p["value"], "model": m["value"],
                                  "pattern_quote": p["quote"], "model_quote": m["quote"]})
                fields[name] = {"value": m["value"], "source": "model (conflict)", "quote": m["quote"]}
        elif m:
            fields[name] = {"value": m["value"], "source": "model", "quote": m["quote"]}
        elif p:
            fields[name] = {"value": p["value"], "source": "pattern", "quote": p["quote"]}
    return {"file": {k: v["value"] for k, v in fields.items()}, "fields": fields, "conflicts": conflicts, "dropped": dropped}


def extract(text: str, llm: NemotronClient | None = None) -> dict:
    pat = pattern_extract(text)
    mod: dict[str, dict] = {}
    error = None
    if llm is not None:
        try:
            mod = model_extract(llm, text)
        except LLMError as e:
            error = str(e)
    out = reconcile(pat, mod)
    out["extractors"] = {"pattern": len(pat), "model": len(mod), "model_error": error}
    return out

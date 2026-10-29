"""Rate book: the Renewal Radar rate-watch dataset (Bank of Canada Valet + lenders' own published rates).

``data/rates_5yr.csv`` is a long table (date, series, term_months, label, rate, source, source_id) with:

* ``policy_rate`` (BoC target overnight), ``prime``, ``goc_bond_yield`` (2/3/5/7/10-year benchmarks)
* ``big6_typical_posted`` (BoC's typical Big-6 posted 1/3/5-year conventional rates)
* ``actual_rate_new_*`` / ``actual_rate_outstanding_*`` (BoC A4 effective rates, insured/uninsured)
* ``bank_posted`` / ``bank_special`` (rates captured from each Big-6 bank's own site by Renewal Radar)
* ``bank_posted_gap_fill`` (posted rates carried forward between captures; flagged, never mixed silently)

Every value returned carries its date and source so the model can cite it and the verifier can trace it.
"""
from __future__ import annotations

import csv
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
BANKS = ("RBC", "TD", "Scotiabank", "BMO", "CIBC", "National Bank")
BANK_ALIASES = {"rbc": "RBC", "royal": "RBC", "td": "TD", "scotia": "Scotiabank", "scotiabank": "Scotiabank",
                "bns": "Scotiabank", "bmo": "BMO", "cibc": "CIBC", "nbc": "National Bank", "national": "National Bank",
                "national bank": "National Bank"}


@lru_cache(maxsize=1)
def _rows() -> tuple[dict, ...]:
    with open(DATA / "rates_5yr.csv", newline="", encoding="utf-8") as f:
        out = []
        for r in csv.DictReader(f):
            try:
                r["rate"] = float(r["rate"])
            except (TypeError, ValueError):
                continue
            r["term_months"] = int(r["term_months"]) if r["term_months"] not in ("", None) else None
            out.append(r)
    return tuple(out)


def canonical_bank(name: str) -> str | None:
    n = (name or "").strip().lower()
    if n in BANK_ALIASES:
        return BANK_ALIASES[n]
    for k, v in BANK_ALIASES.items():
        if k in n:
            return v
    return None


def series(name: str, *, term_months: int | None = None, label: str | None = None) -> list[dict]:
    rows = [r for r in _rows() if r["series"] == name
            and (term_months is None or r["term_months"] == term_months)
            and (label is None or r["label"] == label)]
    return sorted(rows, key=lambda r: r["date"])


def _pick(rows: list[dict], on: str | None) -> dict | None:
    if not rows:
        return None
    if on is None:
        return rows[-1]
    i = bisect_right([r["date"] for r in rows], on)
    return rows[i - 1] if i else None


def _out(r: dict | None) -> dict | None:
    if r is None:
        return None
    return {"date": r["date"], "series": r["series"], "term_months": r["term_months"], "label": r["label"],
            "rate": r["rate"], "source": r["source"], "source_id": r["source_id"]}


def policy_rate(on: str | None = None) -> dict | None:
    return _out(_pick(series("policy_rate"), on))


def prime(on: str | None = None) -> dict | None:
    return _out(_pick(series("prime"), on))


def goc_yield(term_months: int = 60, on: str | None = None) -> dict | None:
    return _out(_pick(series("goc_bond_yield", term_months=term_months), on))


def big6_typical_posted(term_months: int = 60, on: str | None = None) -> dict | None:
    return _out(_pick(series("big6_typical_posted", term_months=term_months), on))


def bank_posted_table(bank: str, on: str | None = None, *, allow_gap_fill: bool = True) -> dict:
    """{term_months: rate} of a Big-6 bank's posted rates on or before ``on``.

    Uses the bank's own captured rates; falls back to labelled gap-fill values per term if allowed."""
    b = canonical_bank(bank)
    if b is None:
        raise ValueError(f"not a Big-6 bank in the rate book: {bank!r}")
    table, provenance = {}, {}
    terms = sorted({r["term_months"] for r in _rows() if r["series"] in ("bank_posted", "bank_posted_gap_fill")
                    and r["label"] == b and r["term_months"]})
    for t in terms:
        r = _pick(series("bank_posted", term_months=t, label=b), on)
        kind = "captured"
        if r is None and allow_gap_fill:
            r, kind = _pick(series("bank_posted_gap_fill", term_months=t, label=b), on), "gap_fill"
        if r is not None:
            table[t] = r["rate"]
            provenance[t] = {"date": r["date"], "kind": kind, "source": r["source"]}
    return {"bank": b, "as_of": on, "posted": table, "provenance": provenance}


def bank_special_table(bank: str, on: str | None = None) -> dict:
    b = canonical_bank(bank)
    if b is None:
        raise ValueError(f"not a Big-6 bank in the rate book: {bank!r}")
    table, provenance = {}, {}
    terms = sorted({r["term_months"] for r in _rows() if r["series"] == "bank_special" and r["label"] == b and r["term_months"]})
    for t in terms:
        r = _pick(series("bank_special", term_months=t, label=b), on)
        if r is not None:
            table[t] = r["rate"]
            provenance[t] = {"date": r["date"], "source": r["source"]}
    return {"bank": b, "as_of": on, "special": table, "provenance": provenance}


def market_snapshot(on: str | None = None) -> dict:
    """Policy rate, prime, GoC curve, Big-6 typical posted and new-lending effective rates."""
    curve = {t: goc_yield(t, on) for t in (24, 36, 60, 84, 120)}
    eff = {}
    for s in ("actual_rate_new_insured", "actual_rate_new_uninsured"):
        eff[s] = {t: _out(_pick(series(s, term_months=t), on)) for t in (0, 60)}
    five = curve[60]
    unins5 = eff["actual_rate_new_uninsured"][60]
    spread = None
    if five and unins5:
        spread = {"value_pct_points": round(unins5["rate"] - five["rate"], 2),
                  "definition": "BoC new uninsured 5y+ fixed effective rate minus GoC 5-year benchmark yield",
                  "dates": [unins5["date"], five["date"]]}
    return {"policy_rate": policy_rate(on), "prime": prime(on), "goc_curve": curve,
            "big6_typical_posted_5y": big6_typical_posted(60, on), "effective_new_lending": eff,
            "fixed_mortgage_spread": spread}


def history(name: str, *, term_months: int | None = None, label: str | None = None, start: str | None = None,
            end: str | None = None, every: int = 1) -> list[dict]:
    rows = [r for r in series(name, term_months=term_months, label=label)
            if (start is None or r["date"] >= start) and (end is None or r["date"] <= end)]
    return [{"date": r["date"], "rate": r["rate"]} for r in rows[::max(1, every)]]


def rate_change(name: str, *, term_months: int | None = None, start: str, end: str | None = None, label: str | None = None) -> dict:
    rows = series(name, term_months=term_months, label=label)
    a, b = _pick(rows, start), _pick(rows, end)
    if a is None or b is None:
        raise ValueError(f"no {name} data for that range")
    return {"series": name, "term_months": term_months, "from": _out(a), "to": _out(b),
            "change_pct_points": round(b["rate"] - a["rate"], 2)}


@lru_cache(maxsize=1)
def lender_directory() -> tuple[dict, ...]:
    """Ontario lender directory with OSFI residential-mortgage book sizes (Renewal Radar data)."""
    with open(DATA / "ontario_lenders.csv", newline="", encoding="utf-8") as f:
        rows = []
        for r in csv.DictReader(f):
            try:
                book = float(r.get("residential_mortgages_$M") or 0) or None
            except ValueError:
                book = None
            rows.append({"id": r["id"], "lender": r["lender"], "group": r["group"], "homepage": r["homepage"],
                         "rates_url": r["rates_url"] or None, "penalty_url": r["penalty_url"] or None,
                         "has_penalty_policy": r["has_policy"] == "True", "residential_book_$M": book,
                         "book_source": r.get("book_source") or None})
    return tuple(rows)


def find_lenders(query: str = "", group: str | None = None, limit: int = 20) -> list[dict]:
    q = (query or "").lower()
    out = [r for r in lender_directory() if (not q or q in r["lender"].lower()) and (group is None or r["group"] == group)]
    out.sort(key=lambda r: -(r["residential_book_$M"] or 0))
    return out[:limit]

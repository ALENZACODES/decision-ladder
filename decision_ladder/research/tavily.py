"""Live market and policy research with Tavily, restricted to primary Canadian sources.

The rate book is a dated snapshot. Tavily fills the gap between the snapshot and today: a Bank of Canada
decision last week, a new OSFI or FSRA notice, a lender changing its posted rates. Results are restricted
to an allow-list of official domains by default, truncated, and returned with URLs so every sentence the
model writes from them can be cited.

Standard library only (POST https://api.tavily.com/search). Set ``TAVILY_API_KEY``.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

ENDPOINT = "https://api.tavily.com/search"
EXTRACT_ENDPOINT = "https://api.tavily.com/extract"

OFFICIAL_DOMAINS = [
    "bankofcanada.ca", "osfi-bsif.gc.ca", "canada.ca", "fsrao.ca", "cmhc-schl.gc.ca", "fcac-acfc.gc.ca",
    "statcan.gc.ca", "bcfsa.ca", "reca.ca", "fin.gc.ca",
]
LENDER_DOMAINS = [
    "rbcroyalbank.com", "td.com", "scotiabank.com", "bmo.com", "cibc.com", "nbc.ca", "firstnational.ca",
    "mcap.com", "eqbank.ca", "hometrust.ca", "meridiancu.ca", "desjardins.com",
]


class ResearchError(RuntimeError):
    pass


@dataclass
class Source:
    title: str
    url: str
    content: str
    score: float
    published: str | None = None

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "content": self.content, "score": self.score,
                "published": self.published}


def _http(payload: dict, api_key: str, timeout: float = 30.0, endpoint: str = ENDPOINT) -> dict:
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise ResearchError(f"Tavily HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from None
    except urllib.error.URLError as e:
        raise ResearchError(f"cannot reach Tavily: {e.reason}") from None


class Research:
    def __init__(self, api_key: str | None = None, transport: Callable[[dict], dict] | None = None,
                 max_results: int = 5, snippet_chars: int = 700,
                 extract_transport: Callable[[dict], dict] | None = None):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        if transport is None and not self.api_key:
            raise ResearchError("TAVILY_API_KEY is not set")
        self.transport = transport or (lambda p: _http(p, self.api_key))  # type: ignore[arg-type]
        if extract_transport is None:
            extract_transport = (offline_extract_transport if transport is offline_transport
                                 else (lambda p: _http(p, self.api_key, 45.0, EXTRACT_ENDPOINT)))  # type: ignore[arg-type]
        self.extract_transport = extract_transport
        self.offline = transport is offline_transport
        self.max_results = max_results
        self.snippet_chars = snippet_chars
        self.calls = 0

    def search(self, query: str, *, scope: str = "official", days: int | None = None,
               include_answer: bool = False) -> dict:
        domains = {"official": OFFICIAL_DOMAINS, "lenders": LENDER_DOMAINS,
                   "both": OFFICIAL_DOMAINS + LENDER_DOMAINS}.get(scope)
        payload: dict = {"query": query[:400], "search_depth": "advanced", "max_results": self.max_results,
                         "include_answer": include_answer}
        if domains:
            payload["include_domains"] = domains
        if days:
            payload["topic"] = "news"
            payload["days"] = int(days)
        self.calls += 1
        raw = self.transport(payload)
        sources = []
        for r in raw.get("results", [])[: self.max_results]:
            sources.append(Source(r.get("title", "")[:200], r.get("url", ""),
                                  (r.get("content") or "")[: self.snippet_chars], float(r.get("score") or 0.0),
                                  r.get("published_date")))
        return {"query": query, "scope": scope, "answer": raw.get("answer") if include_answer else None,
                "sources": [s.to_dict() for s in sources]}


    def extract(self, urls: list[str], *, query: str | None = None, depth: str = "advanced", chunks: int = 3) -> dict:
        """Tavily Extract: the readable content of specific pages (up to 20 URLs), optionally reranked to the
        chunks most relevant to ``query``."""
        payload: dict = {"urls": urls[:20], "extract_depth": depth}
        if query:
            payload["query"] = query[:300]
            payload["chunks_per_source"] = max(1, min(5, chunks))
        self.calls += 1
        raw = self.extract_transport(payload)
        return {"results": [{"url": r.get("url"), "content": (r.get("raw_content") or "")[:12000]}
                            for r in raw.get("results", [])],
                "failed": [f.get("url") if isinstance(f, dict) else f for f in raw.get("failed_results", [])]}


_FIVE_YEAR = re.compile(r"5[\s-]?(?:year|yr)\b[^%\n]{0,90}?(\d{1,2}\.\d{2,3})\s?%", re.I)


def five_year_rates(text: str) -> list[float]:
    """Every rate quoted next to a 5-year label on a page (posted, special, fixed or variable)."""
    out = []
    for m in _FIVE_YEAR.finditer(text or ""):
        v = float(m.group(1))
        if 0.5 <= v <= 15 and v not in out:
            out.append(v)
    return out


def lender_rate_check(research: "Research", bank: str) -> dict:
    """Is the rate book's posted 5-year rate for ``bank`` still what the bank's own rate page shows?

    1. The rate book gives the last captured posted 5-year rate and its capture date.
    2. Tavily Extract reads the bank's mortgage-rate page (URL from the lender directory).
    3. Every rate quoted beside a 5-year label is collected; the book value is CONFIRMED if it appears.
    Nothing here changes a calculation: a stale book value is reported for the broker to refresh."""
    from ..engines import ratebook
    b = ratebook.canonical_bank(bank)
    if b is None:
        raise ValueError(f"not a Big-6 bank: {bank!r}")
    tbl = ratebook.bank_posted_table(b)
    book = tbl["posted"].get(60)
    prov = (tbl["provenance"] or {}).get(60) or {}
    row = next((r for r in ratebook.lender_directory() if ratebook.canonical_bank(r["lender"]) == b and r.get("rates_url")), None)
    url = row["rates_url"] if row else None
    if not url:
        return {"bank": b, "status": "no_rate_page_on_file", "rate_book_5y_posted": book}
    ex = research.extract([url], query=f"{b} 5 year fixed posted mortgage rate")
    text = " ".join(r["content"] for r in ex["results"])
    found = five_year_rates(text)
    status = ("unreadable" if not text else "confirmed" if book is not None and book in found
              else "changed_or_not_shown" if found else "no_5_year_rate_found")
    return {"bank": b, "url": url, "status": status, "rate_book_5y_posted": book,
            "rate_book_captured": prov.get("date"), "rate_book_kind": prov.get("kind"),
            "five_year_rates_on_page": found[:12], "failed": ex["failed"], "offline": research.offline,
            "method": "Tavily Extract of the lender's own rate page; rates beside a 5-year label are compared with the rate book"}


def offline_extract_transport(payload: dict) -> dict:
    """Deterministic stand-in for Tavily Extract (labelled): returns a fixture page, never a live one."""
    return {"results": [{"url": u, "raw_content": "[offline fixture] Run with TAVILY_API_KEY to read the live page."}
                        for u in payload.get("urls", [])], "failed_results": []}


def offline_transport(payload: dict) -> dict:
    """Deterministic stand-in used by tests and the offline demo. Clearly labelled as such."""
    q = payload.get("query", "").lower()
    results = []
    if "bank of canada" in q or "policy rate" in q or "overnight" in q:
        results.append({"title": "[offline fixture] Bank of Canada policy interest rate",
                        "url": "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/",
                        "content": "Offline fixture: the demo does not fetch the live page. Run with TAVILY_API_KEY for live results.",
                        "score": 0.5})
    if "osfi" in q or "stress test" in q or "b-20" in q:
        results.append({"title": "[offline fixture] OSFI Guideline B-20",
                        "url": "https://www.osfi-bsif.gc.ca/en/guidance/guidance-library/residential-mortgage-underwriting-practices-procedures-guideline-2017",
                        "content": "Offline fixture: the demo does not fetch the live page. Run with TAVILY_API_KEY for live results.",
                        "score": 0.5})
    if not results:
        results.append({"title": "[offline fixture] Financial Consumer Agency of Canada: mortgages",
                        "url": "https://www.canada.ca/en/financial-consumer-agency/services/mortgages.html",
                        "content": "Offline fixture: the demo does not fetch the live page. Run with TAVILY_API_KEY for live results.",
                        "score": 0.3})
    return {"results": results}

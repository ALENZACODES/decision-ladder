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
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

ENDPOINT = "https://api.tavily.com/search"

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


def _http(payload: dict, api_key: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), method="POST", headers={
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
                 max_results: int = 5, snippet_chars: int = 700):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        if transport is None and not self.api_key:
            raise ResearchError("TAVILY_API_KEY is not set")
        self.transport = transport or (lambda p: _http(p, self.api_key))  # type: ignore[arg-type]
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

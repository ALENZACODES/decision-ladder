"""Provenance verifier: every number the model writes must come from a tool result or the user.

The verifier extracts numeric claims from the model's text (dollars, percentages, plain numbers with
units), and looks for each one in the evidence: tool outputs and the user's own input. A figure is
*supported* when it matches an evidence value after allowing for display rounding (e.g. 3343.27 may be
written $3,343 or $3.3K). Unsupported figures are reported; the caller decides whether to block, repair or
annotate the answer.

This is deliberately conservative: years, dates, list numbering and small counts are ignored, because
flagging them would bury the real problem (an invented dollar amount or rate) in noise.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

_NUM = re.compile(
    r"(?P<cur>\$|CAD\s?|C\$)?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?(?P<suf>[kKmM](?![a-zA-Z])|million|thousand)?\s?(?P<pct>%|percent|pp|percentage points|bps)?")
# Month-day dates are matched case-sensitively and the day must not continue as a number, so "APR 4.19%" is a
# rate, not "April 4".
_DATE = re.compile(r"\b(?:19|20)\d{2}-\d{2}(?:-\d{2})?\b|"
                   r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?![\d.%])(?:,\s*\d{4})?")


@dataclass
class Claim:
    text: str
    value: float
    kind: str  # money | pct | number
    supported: bool = False
    matched: float | None = None


@dataclass
class Report:
    claims: list[Claim] = field(default_factory=list)

    @property
    def unsupported(self) -> list[Claim]:
        return [c for c in self.claims if not c.supported]

    @property
    def ok(self) -> bool:
        return not self.unsupported

    def to_dict(self) -> dict:
        return {"ok": self.ok, "checked": len(self.claims), "supported": len(self.claims) - len(self.unsupported),
                "unsupported": [{"text": c.text, "value": c.value, "kind": c.kind} for c in self.unsupported]}


def _flatten(x, out: list[float]) -> None:
    if isinstance(x, bool) or x is None:
        return
    if isinstance(x, (int, float)):
        out.append(float(x))
    elif isinstance(x, str):
        for m in re.finditer(r"-?\d+(?:\.\d+)?", x.replace(",", "")):
            try:
                out.append(float(m.group()))
            except ValueError:
                pass
    elif isinstance(x, dict):
        for v in x.values():
            _flatten(v, out)
    elif isinstance(x, (list, tuple)):
        for v in x:
            _flatten(v, out)


def evidence_values(*sources) -> list[float]:
    vals: list[float] = []
    for s in sources:
        if isinstance(s, str):
            try:
                s = json.loads(s)
            except (json.JSONDecodeError, ValueError):
                pass
        _flatten(s, vals)
    # derived values people naturally write: absolute values and x100 / /100 for ratio<->percent
    extra = []
    for v in vals:
        extra.append(abs(v))
        if 0 < abs(v) < 1:
            extra.append(abs(v) * 100)
    return vals + extra


# Thousands written with a thin, narrow no-break or no-break space ("$710 000", seen live) read as "710,000".
_SPACED_THOUSANDS = re.compile(r"(?<=\d)[\u00a0\u2009\u202f](?=\d{3}(?!\d))")


def extract_claims(text: str) -> list[Claim]:
    t = _DATE.sub(" ", _SPACED_THOUSANDS.sub(",", text or ""))
    claims: list[Claim] = []
    for m in _NUM.finditer(t):
        raw = m.group("num")
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        suf = (m.group("suf") or "").lower()
        if suf in ("k", "thousand"):
            v *= 1_000
        elif suf in ("m", "million"):
            v *= 1_000_000
        cur, pct = m.group("cur"), m.group("pct")
        start = m.start("num")
        prev = t[max(0, start - 1):start]
        if pct == "bps":
            kind, v = "pct", v / 100
        elif pct:
            kind = "pct"
        elif cur:
            kind = "money"
        else:
            kind = "number"
        # skip noise: years, short counts, numbered list items, version-ish tokens, rung numbers
        if kind == "number":
            if 1900 <= v <= 2100 and "." not in raw:
                continue
            if v < 100 and "." not in raw:
                continue
            if prev in ("#", "v", "B", "-"):
                continue
        claims.append(Claim(m.group(0).strip(), v, kind))
    return claims


def _matches(v: float, e: float, kind: str) -> bool:
    if e == 0:
        return v == 0
    if kind == "pct":
        return abs(v - e) <= 0.051 or abs(round(e, 1) - v) < 1e-9 or abs(round(e) - v) < 1e-9
    if abs(v - e) <= 0.51:
        return True
    rel = abs(v - e) / abs(e)
    if v >= 1000 and rel <= 0.005:  # "$3,343" for 3343.27; "$25.1K" for 25,110
        return True
    for nd in (-2, -3, -4, -5):  # rounded to hundreds / thousands / ...
        if round(e, nd) == v and v != 0:
            return True
    return False


def verify(text: str, *evidence) -> Report:
    vals = evidence_values(*evidence)
    rep = Report(extract_claims(text))
    for c in rep.claims:
        for e in vals:
            if _matches(c.value, e, c.kind):
                c.supported, c.matched = True, e
                break
    return rep


def annotate(text: str, report: Report) -> str:
    """Mark unsupported figures inline so a reader can never mistake them for calculated values."""
    out = _SPACED_THOUSANDS.sub(",", text)
    for t in dict.fromkeys(c.text for c in report.unsupported):   # each distinct figure once, every occurrence
        out = re.sub(r"(?<![\d.,$])" + re.escape(t) + r"(?![\d])", lambda m: m.group(0) + " [unverified]", out)
    return out

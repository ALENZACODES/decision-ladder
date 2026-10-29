"""Climb the ladder, then let Nemotron reason over what the calculators found.

Order of work for one file:

1. (optional) Nemotron Nano turns a free-text client email into a structured file (``intake.extract``).
2. Every rung runs deterministically. A rung that crashes becomes ``REFER`` with the error, never a pass.
3. (optional) Tavily research pulls anything newer than the rate book (BoC decisions, OSFI/FSRA notices).
4. Nemotron Super writes the broker decision memo from the rung results. The provenance verifier checks
   every figure in the memo against the rung evidence; one repair round, then unsupported figures are
   marked ``[unverified]``.
5. Nemotron Nano drafts the borrower message; the guardrail rung re-runs on that draft.
"""
from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from ..agent import verify
from ..agent.loop import draft_borrower_message
from ..llm.client import LLMError, NemotronClient
from . import rungs as R

MEMO_SYSTEM = """You write the credit decision memo for a licensed Canadian mortgage broker.
You receive the results of a deterministic "decision ladder" that walked one client file through every stage of a
Canadian mortgage (intake, screening, documents, affordability, pre-underwriting readiness, insurance, B-20 qualification,
cross-checks between independent engines, lender fit, property value, cash to close, market, exit cost, renewal outlook,
commercial screen, compliance, decision). Each rung says which of the broker's apps computed it ("computed_by"). Write:
1. VERDICT - one line, using the verdict from the decision rung exactly.
2. WHY - 3 to 5 bullets, the rungs that drove the verdict, citing their figures and naming the app that computed each.
3. PATH TO YES - if options are listed, the 2 most practical ones with their figures; else "Not needed".
4. CONDITIONS & RISKS - bullets.
5. NEXT ACTIONS FOR THE BROKER - numbered, concrete.
Rules: use ONLY figures that appear in the ladder JSON (you may round to the nearest dollar or 0.1%).
No new arithmetic. Do not promise approval or quote a rate as an offer. Under 320 words. Plain text, no markdown tables."""


@dataclass
class LadderRun:
    file: dict
    rungs: list[dict]
    verdict: str
    memo: str = ""
    memo_source: str = "none"
    memo_model: str | None = None
    memo_verification: dict = field(default_factory=dict)
    message: dict | None = None
    research: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    timings_ms: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"file": self.file, "rungs": self.rungs, "verdict": self.verdict, "memo": self.memo,
                "memo_source": self.memo_source, "memo_model": self.memo_model, "memo_verification": self.memo_verification,
                "message": self.message, "research": self.research, "usage": self.usage,
                "timings_ms": self.timings_ms, "model": self.model}


def _engine_label(key: str) -> dict:
    from .. import modules as OS
    OS.load_all()
    m = OS.MODULES.get(key)
    if m is None:
        return {"module": key, "name": {"decision-ladder": "Decision Ladder core"}.get(key, key), "ui_url": None}
    return {"module": key, "name": m.name, "ui_url": f"/apps/{m.key}/{m.entry}" if m.kind != "data" else None}


def climb(file: dict) -> tuple[list[dict], dict]:
    ctx: dict[str, Any] = {"rungs": {}}
    out: list[dict] = []
    for key, fn, stage, engines in R.LADDER_STAGED:
        t0 = time.perf_counter()
        try:
            res = fn(file, ctx).to_dict()
        except Exception as e:  # a broken rung must never look like a pass
            res = R.RungResult(key, key.replace("_", " ").title(), R.REFER,
                               f"Could not evaluate: {type(e).__name__}: {e}", findings=[
                                   "This rung needs more data or a person to review."],
                               evidence={"error": traceback.format_exception_only(type(e), e)[-1].strip()}).to_dict()
        res["ms"] = round((time.perf_counter() - t0) * 1000, 2)
        res["stage"] = stage
        res["engines"] = [_engine_label(e) for e in engines]
        ctx["rungs"][key] = res
        out.append(res)
    return out, ctx


def _compact(rungs: list[dict]) -> list[dict]:
    """What the model sees: status, summary, metrics, findings and the remediation options. Bulky evidence
    (full rate snapshots, sensitivity tables) stays in the UI."""
    keep = []
    for r in rungs:
        item = {k: r[k] for k in ("key", "title", "status", "summary", "metrics", "findings")}
        item["stage"] = r.get("stage")
        item["computed_by"] = [e["name"] for e in r.get("engines") or []]
        if r["key"] == "decision":
            item["options"] = r["evidence"].get("options", [])
        keep.append(item)
    return keep


def template_memo(rungs: list[dict]) -> str:
    """Deterministic memo used when no model is configured (offline demo) or the model call fails."""
    by = {r["key"]: r for r in rungs}
    d = by["decision"]
    lines = [f"VERDICT: {d['summary']}", "", "WHY:"]
    for r in rungs:
        if r["status"] in (R.FAIL, R.REFER) and r["key"] != "decision":
            lines.append(f"- {r['title']} ({r['status']}): {r['summary']}")
    if len(lines) == 3:
        lines.append("- Every rung passed.")
    opts = d["evidence"].get("options") or []
    lines += ["", "PATH TO YES:"] + ([f"- {o}" for o in opts[:3]] or ["- Not needed"])
    lines += ["", "NEXT ACTIONS FOR THE BROKER:"]
    n = 1
    for r in rungs:
        for fnd in r["findings"][:1]:
            if r["status"] != R.PASS and r["key"] != "decision":
                lines.append(f"{n}. {fnd}")
                n += 1
    if n == 1:
        lines.append("1. Confirm documents and submit to the best-fit lender.")
    return "\n".join(lines)


class LadderEngine:
    def __init__(self, llm: NemotronClient | None = None, research=None):
        self.llm = llm
        self.research = research

    def run(self, file: dict, *, write_memo: bool = True, draft_message: bool = True,
            research_queries: list[str] | None = None) -> LadderRun:
        t0 = time.perf_counter()
        rungs, ctx = climb(file)
        timings = {"ladder": round((time.perf_counter() - t0) * 1000, 1)}
        verdict = rungs[-1]["summary"]
        run = LadderRun(file, rungs, verdict, timings_ms=timings)

        if self.research is not None and research_queries:
            t1 = time.perf_counter()
            for q in research_queries[:3]:
                try:
                    run.research.append(self.research.search(q, days=60))
                except Exception as e:  # research is context, never a blocker
                    run.research.append({"query": q, "error": str(e), "sources": []})
            if file.get("lender"):
                from ..engines import ratebook
                from ..research.tavily import lender_rate_check
                if ratebook.canonical_bank(str(file["lender"])):
                    try:
                        chk = lender_rate_check(self.research, str(file["lender"]))
                        run.research.append({"query": f"{chk['bank']} posted 5-year rate on its own page (Tavily Extract)",
                                             "rate_check": chk,
                                             "sources": [{"title": f"{chk['bank']} mortgage rates page", "url": chk.get("url"),
                                                          "content": f"status: {chk['status']}; rates beside a 5-year label: "
                                                                     f"{chk.get('five_year_rates_on_page')}; rate book: "
                                                                     f"{chk.get('rate_book_5y_posted')}% captured {chk.get('rate_book_captured')}"}]})
                    except Exception as e:  # noqa: BLE001
                        run.research.append({"query": "lender rate check", "error": str(e), "sources": []})
            timings["research"] = round((time.perf_counter() - t1) * 1000, 1)

        if self.llm is not None and write_memo:
            t1 = time.perf_counter()
            payload = {"ladder": _compact(rungs)}
            if run.research:
                payload["research"] = [{"query": r["query"], "sources": [{"title": s["title"], "url": s["url"],
                                                                         "content": s["content"][:400]} for s in r.get("sources", [])]}
                                       for r in run.research]
            user = "LADDER RESULTS (JSON):\n" + json.dumps(payload)
            try:
                memo_model = self.llm.ultra
                try:   # the brief: "reach for Nemotron 3 Ultra when you need serious reasoning"
                    res = self.llm.chat([{"role": "system", "content": MEMO_SYSTEM}, {"role": "user", "content": user}],
                                        model=memo_model, max_tokens=1100, purpose="memo")
                except LLMError as e:
                    # only a missing/unsupported model is worth retrying on the reasoner (not auth or rate errors)
                    if memo_model == self.llm.reasoner or getattr(e, "status", None) not in (400, 404, 422):
                        raise
                    memo_model = self.llm.reasoner
                    res = self.llm.chat([{"role": "system", "content": MEMO_SYSTEM}, {"role": "user", "content": user}],
                                        model=memo_model, max_tokens=1100, purpose="memo")
                run.memo_model = memo_model
                memo = res.content
                rep = verify.verify(memo, payload, file)
                if not rep.ok:
                    bad = ", ".join(c.text for c in rep.unsupported)
                    fix = self.llm.chat([{"role": "system", "content": MEMO_SYSTEM}, {"role": "user", "content": user},
                                         {"role": "assistant", "content": memo},
                                         {"role": "user", "content": f"These figures are not in the ladder JSON: {bad}. Rewrite without them."}],
                                        model=memo_model, max_tokens=1100, purpose="memo-repair")
                    rep2 = verify.verify(fix.content, payload, file)
                    if fix.content and len(rep2.unsupported) <= len(rep.unsupported):
                        memo, rep = fix.content, rep2
                    memo = verify.annotate(memo, rep)
                run.memo, run.memo_verification = memo, rep.to_dict()
                run.memo_source = "offline stand-in (no model)" if self.llm.offline else "nemotron"
            except LLMError as e:
                run.memo, run.memo_source = template_memo(rungs), f"template (model error: {e})"
                run.memo_verification = verify.verify(run.memo, rungs, file).to_dict()
            timings["memo"] = round((time.perf_counter() - t1) * 1000, 1)
        elif write_memo:
            run.memo, run.memo_source = template_memo(rungs), "template (no model configured)"
            run.memo_verification = verify.verify(run.memo, rungs, file).to_dict()

        if self.llm is not None and draft_message and file.get("borrower_name"):
            t1 = time.perf_counter()
            facts = {"first_name": str(file["borrower_name"]).split()[0], "purpose": file.get("purpose", "purchase"),
                     "status": {"GO": "file looks ready", "GO WITH CONDITIONS": "we need a few items",
                                "RESTRUCTURE": "we want to review options together",
                                "DECLINE AS STRUCTURED": "we want to review options together"}.get(verdict, "update")}
            try:
                run.message = draft_borrower_message(self.llm, purpose="status update on mortgage file", facts=facts)
            except LLMError as e:
                run.message = {"error": str(e)}
            if run.message and "draft" in run.message:
                ctx["outbound_message"] = run.message["draft"]
                comp = R.rung_compliance(file, ctx).to_dict()
                comp["ms"] = 0.0
                run.rungs = [comp if r["key"] == "compliance" else r for r in run.rungs]
            timings["message"] = round((time.perf_counter() - t1) * 1000, 1)

        if self.llm is not None:
            run.usage = self.llm.usage.to_dict()
            run.model = {"reasoner": self.llm.reasoner, "fast": self.llm.fast, "ultra": self.llm.ultra,
                         "offline": self.llm.offline}
        timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
        return run

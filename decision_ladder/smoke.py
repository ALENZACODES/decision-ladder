"""Live smoke test: proves the system runs on Nebius Token Factory with an NVIDIA open model.

Run on any machine with internet access:

    export NEBIUS_API_KEY=...            # tokenfactory.nebius.com -> API keys
    export TAVILY_API_KEY=...            # optional
    python -m decision_ladder smoke

It (1) lists your models and confirms the configured Nemotron IDs exist, (2) asks Nemotron Super a tool
question and checks a tool was called, (3) runs Nemotron Nano JSON extraction, (4) runs a full ladder with
a memo, (5) optionally hits Tavily. Results are written to ``smoke_report.json`` (no API keys in it).
"""
from __future__ import annotations

import json
import os
import time


def run_smoke() -> int:
    from .agent.loop import Copilot
    from .intake.extract import extract
    from .ladder.runner import LadderEngine
    from .llm.client import LLMError, NemotronClient
    from .research.tavily import Research
    from .samples import SAMPLE_EMAIL, SAMPLES

    report: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "checks": []}

    def check(name: str, ok: bool, detail) -> None:
        report["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {json.dumps(detail, default=str)[:300]}")

    try:
        llm = NemotronClient()
    except LLMError as e:
        print(f"[FAIL] {e}")
        return 2
    report["base_url"], report["reasoner"], report["fast"] = llm.base_url, llm.reasoner, llm.fast

    try:
        ids = llm.list_models()
        nv = [i for i in ids if "nemotron" in i.lower() or i.lower().startswith("nvidia/")]
        check("models visible", bool(ids), {"count": len(ids), "nvidia": nv})
        res = llm.resolve_models()
        check("NVIDIA Nemotron reasoner resolved", "nemotron" in llm.reasoner.lower() and llm.reasoner in ids, res)
        check("NVIDIA Nemotron fast model resolved", "nemotron" in llm.fast.lower() and llm.fast in ids,
              {"fast": llm.fast, "reason": res["fast_reason"]})
        report["resolved_models"] = res
        if res["reasoner_reason"] != "configured" or res["fast_reason"] != "configured":
            print(f"  note: set DL_MODEL_REASONER={llm.reasoner} DL_MODEL_FAST={llm.fast} to pin these")
    except LLMError as e:
        check("models visible", False, str(e))

    try:
        res = Copilot(llm).ask("A client earns 150000, wants a 900000 home with 90000 down at 4.29% over 25 years with "
                               "900 a month of car and card payments and 6000 property tax. Do they pass the stress "
                               "test, and if not what are the options?")
        tools_used = [s.name for s in res.steps if s.kind in ("tool", "repair")]
        check("Nemotron tool calling", bool(tools_used), tools_used)
        check("copilot figures traced", res.verification["ok"], res.verification)
        report["copilot_answer"] = res.answer
    except LLMError as e:
        check("Nemotron tool calling", False, str(e))

    try:
        ex = extract(SAMPLE_EMAIL, llm)
        check("Nemotron Nano JSON extraction", ex["extractors"]["model"] > 0 and not ex["extractors"]["model_error"],
              {"model_fields": ex["extractors"]["model"], "conflicts": ex["conflicts"], "dropped": ex["dropped"]})
    except LLMError as e:
        check("Nemotron Nano JSON extraction", False, str(e))

    run = LadderEngine(llm).run({k: v for k, v in SAMPLES["oakville_stretch"].items() if k != "label"})
    check("ladder memo by Nemotron", run.memo_source == "nemotron", {"source": run.memo_source, "verdict": run.verdict})
    check("memo figures traced", run.memo_verification.get("ok"), run.memo_verification)
    report["memo"] = run.memo

    if os.environ.get("TAVILY_API_KEY"):
        try:
            r = Research().search("Bank of Canada interest rate announcement", days=60)
            check("Tavily research", bool(r["sources"]), [s["url"] for s in r["sources"]])
        except Exception as e:  # noqa: BLE001
            check("Tavily research", False, str(e))

    report["usage"] = llm.usage.to_dict()
    report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open("smoke_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    fails = [c for c in report["checks"] if not c["ok"]]
    print(f"\n{len(report['checks']) - len(fails)}/{len(report['checks'])} checks passed. Usage: {report['usage']}")
    print("Wrote smoke_report.json")
    return 1 if fails else 0

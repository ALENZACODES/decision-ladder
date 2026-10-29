"""Evaluation harness for the copilot.

For each case in ``evals/cases.json`` it measures:

* **tool selection**: did the model call at least one of the expected tools?
* **answer accuracy**: does the answer contain the key figure(s)? Expected figures are computed by calling
  the deterministic tool directly (``expect_from``), never typed by hand.
* **provenance**: did every figure in the answer trace to a tool result (verifier ok)?
* latency, tokens and approximate cost.

Writes ``eval_report.json`` and prints a table. In offline mode the scripted stand-in is evaluated, which
tests the plumbing only; the numbers that matter come from a live run against Nemotron.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .agent import tools as T
from .agent import verify

CASES = Path(__file__).resolve().parent.parent / "evals" / "cases.json"


def _get(obj, path: str):
    for part in path.split("."):
        if isinstance(obj, list):
            obj = obj[int(part)]
        elif isinstance(obj, dict):
            obj = obj.get(part) if part in obj else obj.get(int(part)) if part.isdigit() and int(part) in obj else obj.get(part)
        else:
            return None
        if obj is None:
            return None
    return obj


def expected_numbers(case: dict) -> list[float]:
    ef = case.get("expect_from")
    if not ef:
        return []
    out = T.run(ef["tool"], ef["args"])
    vals = []
    for p in ef["paths"]:
        v = _get(out, p)
        if v is not None:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
    return vals


def answer_has(answer: str, value: float) -> bool:
    claims = verify.extract_claims(answer)
    return any(verify._matches(c.value, value, c.kind) or verify._matches(c.value, abs(value), c.kind) for c in claims)


def run_evals(llm, offline: bool = False, cases_path: Path = CASES, research=None) -> int:
    from .agent.loop import Copilot
    cases = json.loads(cases_path.read_text())["cases"]
    rows = []
    for c in cases:
        cop = Copilot(llm, research)
        t0 = time.perf_counter()
        before = dict(llm.usage.to_dict())
        try:
            res = cop.ask(c["question"])
            err = None
        except Exception as e:  # noqa: BLE001 - an eval must record failures, not stop
            res, err = None, f"{type(e).__name__}: {e}"
        ms = (time.perf_counter() - t0) * 1000
        exp = expected_numbers(c)
        if res is None:
            rows.append({"id": c["id"], "error": err, "ms": round(ms)})
            continue
        called = [s.name for s in res.steps if s.kind in ("tool", "repair", "research")]
        tool_ok = any(t in called for t in c["expect_tools"])
        acc = all(answer_has(res.answer, v) for v in exp) if exp else None
        after = llm.usage.to_dict()
        rows.append({"id": c["id"], "tool_ok": tool_ok, "tools": called, "accuracy": acc, "expected": exp,
                     "provenance_ok": res.verification["ok"], "repaired": res.repaired, "ms": round(ms),
                     "tokens": after["prompt_tokens"] + after["completion_tokens"] - before["prompt_tokens"] - before["completion_tokens"],
                     "answer": res.answer})
    done = [r for r in rows if "error" not in r]
    acc_rows = [r for r in done if r["accuracy"] is not None]
    summary = {
        "mode": "offline-scripted" if offline else "live",
        "model": llm.reasoner, "cases": len(rows), "errors": len(rows) - len(done),
        "tool_selection": f"{sum(r['tool_ok'] for r in done)}/{len(done)}",
        "answer_accuracy": f"{sum(bool(r['accuracy']) for r in acc_rows)}/{len(acc_rows)}",
        "provenance_clean": f"{sum(r['provenance_ok'] for r in done)}/{len(done)}",
        "repairs": sum(r["repaired"] for r in done),
        "median_ms": sorted(r["ms"] for r in done)[len(done) // 2] if done else None,
        "usage": llm.usage.to_dict(),
    }
    Path("eval_report.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, default=str))
    print(f"{'case':<22}{'tool':<6}{'acc':<6}{'trace':<7}{'ms':>7}  tools")
    for r in rows:
        if "error" in r:
            print(f"{r['id']:<22}ERROR {r['error'][:80]}")
            continue
        print(f"{r['id']:<22}{'ok' if r['tool_ok'] else 'MISS':<6}{'-' if r['accuracy'] is None else ('ok' if r['accuracy'] else 'MISS'):<6}"
              f"{'ok' if r['provenance_ok'] else 'FLAG':<7}{r['ms']:>7}  {','.join(r['tools'])}")
    print(json.dumps(summary, indent=2))
    print("Wrote eval_report.json")
    return 0

"""Command line.

  python -m decision_ladder serve [PORT] [--offline]   web UI + API
  python -m decision_ladder demo [--offline]           run every sample file up the ladder
  python -m decision_ladder ladder FILE.json           one file (JSON) up the ladder
  python -m decision_ladder intake FILE.txt            free text -> structured file -> ladder
  python -m decision_ladder ask "question"             copilot with tool calling
  python -m decision_ladder book BOOK.csv [AS_OF]      ranked renewal queue
  python -m decision_ladder models                     list models your Token Factory key can use
  python -m decision_ladder smoke                      live end-to-end check against Token Factory
  python -m decision_ladder eval [--offline]           run the evaluation suite (evals/cases.json)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _llm(offline: bool):
    if offline or not os.environ.get("NEBIUS_API_KEY"):
        from .llm.offline import offline_client
        if not offline:
            print("[NEBIUS_API_KEY not set: using the offline scripted stand-in, no model calls]", file=sys.stderr)
        return offline_client()
    from .llm.client import NemotronClient
    return NemotronClient()


def _research(offline: bool):
    from .research.tavily import Research, offline_transport
    if offline or not os.environ.get("TAVILY_API_KEY"):
        return Research(transport=offline_transport)
    return Research()


def _print_run(run: dict) -> None:
    print(f"\n=== {run['file'].get('borrower_name', '')} ({run['file'].get('purpose', 'purchase')}) -> {run['verdict']}")
    for r in reversed(run["rungs"]):
        print(f"  [{r['status']:<5}] {r['title']:<38} {r['summary']}")
    print("\n" + run["memo"])
    v = run.get("memo_verification") or {}
    print(f"\n  memo source: {run['memo_source']} | figures traced: {v.get('supported')}/{v.get('checked')}")
    if run.get("usage"):
        u = run["usage"]
        print(f"  model calls: {u['calls']} | tokens in/out: {u['prompt_tokens']}/{u['completion_tokens']} | approx ${u['approx_cost_usd']}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    offline = "--offline" in argv
    argv = [a for a in argv if a != "--offline"]
    cmd = argv[0] if argv else "help"

    if cmd == "serve":
        from .web.server import serve
        serve(int(argv[1]) if len(argv) > 1 else int(os.environ.get("PORT", 8000)), offline=offline)
        return 0
    if cmd == "demo":
        from .ladder.runner import LadderEngine
        from .samples import SAMPLES
        for f in SAMPLES.values():
            eng = LadderEngine(_llm(offline), _research(offline))
            _print_run(eng.run({k: v for k, v in f.items() if k != "label"}).to_dict())
        return 0
    if cmd == "ladder":
        from .ladder.runner import LadderEngine
        f = json.loads(Path(argv[1]).read_text())
        _print_run(LadderEngine(_llm(offline), _research(offline)).run(f).to_dict())
        return 0
    if cmd == "intake":
        from .intake.extract import extract
        from .ladder.runner import LadderEngine
        text = Path(argv[1]).read_text() if len(argv) > 1 else sys.stdin.read()
        llm = _llm(offline)
        ex = extract(text, llm)
        print(json.dumps({"file": ex["file"], "conflicts": ex["conflicts"], "dropped": ex["dropped"]}, indent=2))
        _print_run(LadderEngine(llm, _research(offline)).run(ex["file"]).to_dict())
        return 0
    if cmd == "ask":
        from .agent.loop import Copilot
        res = Copilot(_llm(offline), _research(offline)).ask(" ".join(argv[1:]))
        for s in res.steps:
            if s.kind != "answer":
                print(f"  -> {s.kind}: {s.name}({json.dumps(s.args)[:160]})")
        print("\n" + res.answer)
        print(f"\n  verification: {res.verification}")
        return 0
    if cmd == "book":
        from .book.scan import scan
        out = scan(Path(argv[1]).read_text(), argv[2] if len(argv) > 2 else None, _llm(offline), 3)
        print(json.dumps(out["summary"], indent=2))
        for r in out["queue"]:
            print(f"  {r['priority']:>5}  {r['tier']:<15} {r['borrower']:<16} {r['lender']:<14} {r['why']}")
        return 0
    if cmd == "models":
        llm = _llm(False)
        ids = llm.list_models()
        for i in ids:
            mark = "  <- NVIDIA" if "nvidia" in i.lower() or "nemotron" in i.lower() else ""
            print(i + mark)
        return 0
    if cmd == "smoke":
        from .smoke import run_smoke
        return run_smoke()
    if cmd == "eval":
        from .evals import run_evals
        return run_evals(_llm(offline), offline=offline or not os.environ.get("NEBIUS_API_KEY"))
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Background jobs, built to run as Nebius Serverless AI Jobs.

    python -m decision_ladder job renewal-book --input book.csv --out /data/out [--as-of 2026-10-28] [--drafts 5]

The overnight renewal-book job scans a broker's whole book (every loan through the exit-cost and switch
rungs, Renewal Radar's lender-exact penalties and the renewal-shock model), ranks the call queue, has
Nemotron Nano draft guardrailed outreach for the top clients, and writes ``renewal_queue.json`` and
``renewal_queue.md`` to ``--out``. A Serverless Job is billed only while it runs and stops when the scan
is done, which suits a nightly batch better than an always-on server. Results must be written to a
mounted container volume (``--out``) or read from the job logs (a one-line JSON summary is printed).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def renewal_book_job(argv: list[str]) -> int:
    import argparse

    from .book.scan import scan
    p = argparse.ArgumentParser(prog="decision_ladder job renewal-book")
    p.add_argument("--input", required=True, help="CSV path (see samples.SAMPLE_BOOK_CSV for the columns)")
    p.add_argument("--out", default=os.environ.get("DL_JOB_OUT", "./job_out"))
    p.add_argument("--as-of", default=None)
    p.add_argument("--drafts", type=int, default=5)
    p.add_argument("--offline", action="store_true")
    a = p.parse_args(argv)
    t0 = time.time()
    text = Path(a.input).read_text(encoding="utf-8")
    llm = None
    if a.drafts > 0:
        from .__main__ import _llm
        llm = _llm(a.offline)
    out = scan(text, a.as_of, llm, a.drafts)
    out["job"] = {"name": "renewal-book", "seconds": round(time.time() - t0, 2),
                  "model_usage": llm.usage.to_dict() if llm else None,
                  "runtime": "nebius-serverless-job" if os.environ.get("NEBIUS_JOB") or os.environ.get("DL_JOB") else "local"}
    d = Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    (d / "renewal_queue.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    (d / "renewal_queue.md").write_text(_markdown(out), encoding="utf-8")
    print(json.dumps({"job": "renewal-book", "loans": out["summary"]["loans"], "call_this_week": out["summary"]["call_this_week"],
                      "errors": len(out["errors"]), "out": str(d.resolve()), "seconds": out["job"]["seconds"]}))
    return 0 if not out["errors"] else 1


def _markdown(out: dict) -> str:
    s = out["summary"]
    lines = [f"# Renewal call queue ({out['as_of']})", "",
             f"{s['loans']} loans, ${s['balance_total']:,.0f} balance; {s['call_this_week']} to call this week, "
             f"{s['call_this_month']} this month; average payment change at renewal {s['avg_payment_change_pct']}%.", "",
             "| Priority | Tier | Borrower | Lender | Balance | Maturity | Why |", "|---|---|---|---|---|---|---|"]
    for r in out["queue"]:
        lines.append(f"| {r['priority']} | {r['tier']} | {r['borrower']} | {r['lender']} | ${r['balance']:,.0f} | "
                     f"{r['maturity']} | {r['why']} |")
    drafts = [r for r in out["queue"] if r.get("outreach", {}).get("send_text")]
    if drafts:
        lines += ["", "## Outreach drafts (Nemotron Nano, guardrail-checked)", ""]
        for r in drafts:
            o = r["outreach"]
            lines.append(f"- **{r['borrower']}**{' (blocked, safe text used)' if o.get('blocked') else ''}: {o['send_text']}")
    if out["errors"]:
        lines += ["", "## Rows with errors", ""] + [f"- {e}" for e in out["errors"]]
    return "\n".join(lines) + "\n"


JOBS = {"renewal-book": renewal_book_job}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in JOBS:
        print(f"usage: python -m decision_ladder job {{{'|'.join(JOBS)}}} [options]", file=sys.stderr)
        return 2
    return JOBS[argv[0]](argv[1:])

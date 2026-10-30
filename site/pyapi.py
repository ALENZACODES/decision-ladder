"""Browser-side API for the GitHub Pages build (runs inside Pyodide).

The static site has no server, so the web UI's POST /api/* calls are answered here, in the visitor's
browser, by the same Python code the server uses (decision_ladder/web/server.py, do_POST), always in
offline mode: no model or research calls leave the browser. The JavaScript apps' calculators run through
pages-bridge.js (the browser version of decision_ladder/modules/bridge.mjs) instead of Node.
"""
from __future__ import annotations

import json
import time

import js  # Pyodide's bridge to the page

from decision_ladder.modules import jsapps


def _call(module: str, fn: str, args: dict) -> dict:
    """Same contract as jsapps.call, but runs the app's JavaScript in the page instead of Node."""
    try:
        out = json.loads(str(js.dlBridgeCall(module, fn, json.dumps(args))))
    except Exception as e:  # noqa: BLE001
        return {"error": f"browser bridge failed: {e}"}
    if not out.get("ok"):
        return {"error": out.get("error") or "bridge failed"}
    res = out["result"]
    if isinstance(res, dict):
        res.setdefault("engine", f"{module} ({fn})")
    return res


jsapps.call = _call
jsapps.node_path = lambda: "browser"

from decision_ladder.agent import tools as T  # noqa: E402
from decision_ladder.agent.loop import Copilot  # noqa: E402
from decision_ladder.book.scan import scan  # noqa: E402
from decision_ladder.intake.documents import read_document  # noqa: E402
from decision_ladder.intake.extract import extract  # noqa: E402
from decision_ladder.ladder.runner import LadderEngine  # noqa: E402
from decision_ladder.llm.client import LLMError  # noqa: E402
from decision_ladder.research.tavily import ResearchError  # noqa: E402
from decision_ladder.web.server import Services  # noqa: E402

svc = Services(offline=True)


def _post(path: str, body: dict):
    if path == "/api/ladder":
        f = body.get("file") or {}
        if not isinstance(f, dict) or not f:
            raise ValueError("file object required")
        eng = LadderEngine(svc.llm(), svc.research())
        qs = ["Bank of Canada interest rate announcement", "OSFI mortgage underwriting B-20 update"] if body.get("research") else None
        return eng.run(f, write_memo=body.get("memo", True), draft_message=body.get("message", True), research_queries=qs).to_dict()
    if path == "/api/intake":
        text = str(body.get("text") or "")[:20000]
        if not text.strip() and not body.get("documents"):
            raise ValueError("text required")
        llm = svc.llm()
        out = extract(text, llm)
        docs = [str(d)[:20000] for d in (body.get("documents") or [])[:6] if str(d).strip()]
        out["documents"] = [read_document(d, llm) for d in docs]
        if body.get("run"):
            f = dict(out["file"])
            if out["documents"]:
                f["documents"] = out["documents"]
            f.setdefault("as_of", time.strftime("%Y-%m-%d"))
            out["ladder"] = LadderEngine(llm, svc.research()).run(f).to_dict()
        out["usage"] = llm.usage.to_dict()
        return out
    if path == "/api/document":
        text = str(body.get("text") or "")[:20000]
        if not text.strip():
            raise ValueError("text required")
        llm = svc.llm()
        out = read_document(text, llm)
        out["usage"] = llm.usage.to_dict()
        return out
    if path == "/api/ask":
        q = str(body.get("question") or "")[:4000]
        if not q.strip():
            raise ValueError("question required")
        cop = Copilot(svc.llm(), svc.research())
        hist = [m for m in (body.get("history") or [])[-8:] if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
        return cop.ask(q, context=body.get("context") or None, history=hist).to_dict()
    if path == "/api/book":
        csv_text = str(body.get("csv") or "")[:200000]
        if not csv_text.strip():
            raise ValueError("csv required")
        drafts = max(0, min(5, int(body.get("drafts", 3))))
        return scan(csv_text, body.get("as_of"), svc.llm() if drafts else None, drafts)
    if path == "/api/tool":
        return T.run(str(body.get("name")), body.get("args") or {})
    return None


def handle(path: str, raw: str) -> str:
    """Returns JSON: {"status": int, "body": <response object>}."""
    try:
        body = json.loads(raw or "{}")
        if not isinstance(body, dict):
            raise ValueError("JSON object expected")
        out = _post(path, body)
        if out is None:
            return json.dumps({"status": 404, "body": {"error": "not found"}})
        return json.dumps({"status": 200, "body": out}, default=str)
    except (ValueError, json.JSONDecodeError) as e:
        return json.dumps({"status": 400, "body": {"error": str(e)}})
    except (LLMError, ResearchError) as e:
        return json.dumps({"status": 502, "body": {"error": f"upstream: {e}"}})

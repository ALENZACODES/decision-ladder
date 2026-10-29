"""HTTP API and web UI (standard library only).

Endpoints (JSON in, JSON out):

  GET  /api/health          mode (live/offline), model IDs, research mode, version
  GET  /api/samples         sample files, sample email, sample renewal book CSV
  GET  /api/tools           tool specs Nemotron sees
  GET  /api/market          rate-book market snapshot
  POST /api/ladder          {file, research?: bool, memo?: bool, message?: bool}  -> ladder run
  POST /api/intake          {text, documents?: [text], run?: bool}                -> extraction (+ ladder run)
  POST /api/document        {text}                                                -> one document read (type, figures, quotes)
  POST /api/ask             {question, context?: {}, history?: []}                -> copilot answer + trace
  POST /api/book            {csv, as_of?: "YYYY-MM-DD", drafts?: int}             -> ranked renewal queue
  POST /api/tool            {name, args}                                          -> direct tool call (no model)

Live mode needs NEBIUS_API_KEY. Without it the server runs the scripted offline stand-in and labels every
model-shaped output as offline. TAVILY_API_KEY enables live research; otherwise labelled fixtures are used.
"""
from __future__ import annotations

import json
import mimetypes
import os
import threading
import time
import urllib.error
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .. import __version__
from ..agent import tools as T
from ..agent.loop import Copilot
from ..book.scan import scan
from ..engines import ratebook
from ..intake.documents import read_document
from ..intake.extract import extract
from ..ladder.runner import LadderEngine
from ..llm.client import LLMError, NemotronClient
from ..llm.offline import offline_client
from ..research.tavily import Research, ResearchError, offline_transport
from ..samples import SAMPLE_BOOK_CSV, SAMPLE_EMAIL, SAMPLES
from ..samples_docs import SAMPLE_DOCS
from .. import modules as OS

STATIC = Path(__file__).resolve().parent / "static"
MAX_BODY = 512 * 1024


class Services:
    """Builds a fresh client per request so usage counters are per-request, and shares config."""

    def __init__(self, offline: bool | None = None):
        self.module_errors = OS.load_all()
        key = os.environ.get("NEBIUS_API_KEY")
        self.live = bool(key) and not (offline or os.environ.get("DL_OFFLINE") == "1")
        self.research_live = bool(os.environ.get("TAVILY_API_KEY"))
        self.resolution: dict | None = None
        if self.live and os.environ.get("DL_RESOLVE_MODELS", "1") == "1":
            try:
                c = NemotronClient()
                self.resolution = c.resolve_models()
                os.environ["DL_MODEL_REASONER"], os.environ["DL_MODEL_FAST"] = c.reasoner, c.fast
                os.environ["DL_MODEL_ULTRA"] = c.ultra
            except LLMError as e:
                self.resolution = {"error": str(e)}

    def llm(self) -> NemotronClient:
        return NemotronClient() if self.live else offline_client()

    def research(self) -> Research:
        return Research() if self.research_live else Research(transport=offline_transport)

    def health(self) -> dict:
        c = self.llm()
        return {"ok": True, "version": __version__, "mode": "live" if self.live else "offline",
                "models": {"reasoner": c.reasoner, "fast": c.fast, "ultra": c.ultra},
                "provider": "Nebius Token Factory" if self.live else "offline scripted stand-in (no model)",
                "base_url": c.base_url if self.live else None,
                "research": "tavily-live" if self.research_live else "offline-fixtures",
                "tools": len(T.TOOLS) + 1, "model_resolution": self.resolution,
                "modules": len(OS.MODULES), "module_errors": self.module_errors,
                "thinking": c.thinking}


class RateLimiter:
    """Per-IP token bucket so a public demo URL cannot drain the Token Factory credits."""

    def __init__(self, per_minute: int = 20):
        self.rate = per_minute / 60.0
        self.cap = float(per_minute)
        self.buckets: dict[str, tuple[float, float]] = {}
        self.lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        with self.lock:
            tokens, last = self.buckets.get(ip, (self.cap, now))
            tokens = min(self.cap, tokens + (now - last) * self.rate)
            if tokens < 1:
                self.buckets[ip] = (tokens, now)
                return False
            self.buckets[ip] = (tokens - 1, now)
            return True


def make_handler(svc: Services, limiter: RateLimiter):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DecisionLadder/" + __version__

        def log_message(self, fmt, *args):  # quieter logs, no bodies (PII)
            if os.environ.get("DL_ACCESS_LOG") == "1":
                super().log_message(fmt, *args)

        # ---------------------------------------------------------- helpers
        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj, default=str).encode())

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise ValueError("request too large")
            raw = self.rfile.read(n) if n else b"{}"
            data = json.loads(raw or b"{}")
            if not isinstance(data, dict):
                raise ValueError("JSON object expected")
            return data

        # ---------------------------------------------------------- routes
        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/health":
                return self._json(svc.health())
            if path == "/api/samples":
                return self._json({"files": SAMPLES, "email": SAMPLE_EMAIL, "book_csv": SAMPLE_BOOK_CSV, "documents": SAMPLE_DOCS})
            if path == "/api/os":
                return self._json(OS.catalog())
            if path.startswith("/apps/"):
                return self._app(path, "GET")
            if path == "/api/tools":
                return self._json({"tools": T.specs()})
            if path == "/api/market":
                return self._json(ratebook.market_snapshot())
            if path == "/api/history":
                return self._json({
                    "policy_rate": ratebook.history("policy_rate", start="2021-01-01", every=5),
                    "goc_5y": ratebook.history("goc_bond_yield", term_months=60, start="2021-01-01", every=5),
                    "posted_5y": ratebook.history("big6_typical_posted", term_months=60, start="2021-01-01"),
                    "new_uninsured_5y": ratebook.history("actual_rate_new_uninsured", term_months=60, start="2021-01-01"),
                })
            return self._static(path)

        def _static(self, path: str):
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            if rel.startswith("static/"):
                rel = rel[len("static/"):]
            target = (STATIC / rel).resolve()
            if not str(target).startswith(str(STATIC)) or not target.is_file():
                return self._json({"error": "not found"}, 404)
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript",):
                ctype += "; charset=utf-8"
            self._send(200, target.read_bytes(), ctype)

        # ---------------------------------------------------------- embedded module apps
        def _app(self, path: str, method: str):
            parts = path.split("/", 3)  # ['', 'apps', key, rest]
            key = parts[2] if len(parts) > 2 else ""
            rest = parts[3] if len(parts) > 3 else ""
            mod = OS.MODULES.get(key)
            if mod is None:
                return self._json({"error": f"unknown module {key!r}"}, 404)
            if mod.kind == "service":
                return self._proxy(mod, rest, method)
            if rest == "" and not path.endswith("/"):
                self.send_response(301)
                self.send_header("Location", f"/apps/{key}/")
                self.end_headers()
                return
            root = mod.web_path.resolve()
            target = (root / (rest or mod.entry)).resolve()
            if target.is_dir():
                target = target / "index.html"
            if not str(target).startswith(str(root)) or not target.is_file():
                return self._json({"error": "not found"}, 404)
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if target.suffix in (".mjs", ".js"):
                ctype = "text/javascript"
            if ctype.startswith("text/") or ctype in ("application/json", "image/svg+xml"):
                ctype += "; charset=utf-8"
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            # embedded apps are the author's own static projects; they may use inline scripts and their own CDNs
            self.send_header("Content-Security-Policy", "frame-ancestors 'self'")
            self.end_headers()
            self.wfile.write(body)

        def _proxy(self, mod, rest: str, method: str):
            try:
                from ..modules import rr_service
            except Exception as e:  # noqa: BLE001
                return self._json({"error": f"service manager unavailable: {e}"}, 503)
            if not rr_service.available():
                started = rr_service.start() if hasattr(rr_service, "start") else False
                if not started and not rr_service.available():
                    return self._json({"error": f"{mod.name} service is not running",
                                       "hint": "install its requirements (modules/renewal-radar/requirements.txt)"}, 503)
            import urllib.request as ur
            qs = urlparse(self.path).query
            url = rr_service.base_url().rstrip("/") + "/" + rest + (("?" + qs) if qs else "")
            data = None
            if method == "POST":
                n = int(self.headers.get("Content-Length") or 0)
                data = self.rfile.read(n) if n else b""
            req = ur.Request(url, data=data, method=method,
                             headers={k: v for k, v in self.headers.items() if k.lower() in ("content-type", "accept")})
            try:
                with ur.urlopen(req, timeout=60) as r:
                    body, code, ctype = r.read(), r.status, r.headers.get("Content-Type", "application/octet-stream")
            except urllib.error.HTTPError as e:
                body, code, ctype = e.read(), e.code, e.headers.get("Content-Type", "application/json")
            except OSError as e:
                return self._json({"error": f"{mod.name} service error: {e}"}, 502)
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            path = urlparse(self.path).path
            if path.startswith("/apps/"):
                return self._app(path, "POST")
            ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()
            if path != "/api/tool" and not limiter.allow(ip):
                return self._json({"error": "rate limited: try again in a minute"}, HTTPStatus.TOO_MANY_REQUESTS)
            try:
                body = self._body()
                if path == "/api/ladder":
                    f = body.get("file") or {}
                    if not isinstance(f, dict) or not f:
                        raise ValueError("file object required")
                    eng = LadderEngine(svc.llm(), svc.research())
                    qs = ["Bank of Canada interest rate announcement", "OSFI mortgage underwriting B-20 update"] if body.get("research") else None
                    run = eng.run(f, write_memo=body.get("memo", True), draft_message=body.get("message", True), research_queries=qs)
                    return self._json(run.to_dict())
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
                    return self._json(out)
                if path == "/api/document":
                    text = str(body.get("text") or "")[:20000]
                    if not text.strip():
                        raise ValueError("text required")
                    llm = svc.llm()
                    out = read_document(text, llm)
                    out["usage"] = llm.usage.to_dict()
                    return self._json(out)
                if path == "/api/ask":
                    q = str(body.get("question") or "")[:4000]
                    if not q.strip():
                        raise ValueError("question required")
                    cop = Copilot(svc.llm(), svc.research())
                    hist = [m for m in (body.get("history") or [])[-8:] if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
                    res = cop.ask(q, context=body.get("context") or None, history=hist)
                    return self._json(res.to_dict())
                if path == "/api/book":
                    csv_text = str(body.get("csv") or "")[:200000]
                    if not csv_text.strip():
                        raise ValueError("csv required")
                    drafts = max(0, min(5, int(body.get("drafts", 3))))
                    return self._json(scan(csv_text, body.get("as_of"), svc.llm() if drafts else None, drafts))
                if path == "/api/tool":
                    return self._json(T.run(str(body.get("name")), body.get("args") or {}))
                return self._json({"error": "not found"}, 404)
            except (ValueError, json.JSONDecodeError) as e:
                return self._json({"error": str(e)}, 400)
            except (LLMError, ResearchError) as e:
                return self._json({"error": f"upstream: {e}"}, 502)

    return Handler


def serve(port: int = 8000, host: str = "0.0.0.0", offline: bool | None = None) -> None:
    svc = Services(offline)
    httpd = ThreadingHTTPServer((host, port), make_handler(svc, RateLimiter(int(os.environ.get("DL_RATE_PER_MIN", "20")))))
    h = svc.health()
    print(f"Decision Ladder {h['version']} on http://{host}:{port}  mode={h['mode']}  reasoner={h['models']['reasoner']}  research={h['research']}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

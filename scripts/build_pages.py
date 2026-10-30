"""Build the static GitHub Pages site for Decision Ladder (no server, no keys).

    python scripts/build_pages.py [OUT_DIR] [--prefix /decision-ladder]

What it writes (default OUT_DIR: _site):
  index.html, static/   the OS web UI, with paths re-rooted under the Pages prefix and site/pages-shim.js added
  api/*.json            GET endpoints (health, samples, os, tools, market, history), produced by the real code
  apps/<key>/           every static module app, served as in the OS
  modsrc/<repo>/        the JavaScript apps' calculator sources used by the tools (pages-bridge.js loads them)
  py/bundle.zip         the Python package + module data; Pyodide runs it in the visitor's browser (offline mode)

POST endpoints (ladder, intake, document, ask, book, tool) run in the browser through site/pyapi.py.
Renewal Radar is a FastAPI service, so its screen links to its own live deployment instead.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.pop("NEBIUS_API_KEY", None)
os.environ.pop("TAVILY_API_KEY", None)

PYODIDE_VERSION = "0.29.5"
RR_LIVE = "https://renewal-radar-nplp.onrender.com/"
TEXT_EXT = {".html", ".js", ".mjs", ".css", ".json", ".svg", ".txt", ".csv", ".md", ".webmanifest"}
BUNDLE_EXT = {".py", ".json", ".csv", ".txt", ".html", ".js", ".mjs", ".sql", ".md", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".ipynb"}
BUNDLE_MAX = 3 * 1024 * 1024
MODULE_EXT = {".py", ".csv", ".json", ".txt", ".sql", ".toml", ".yaml", ".yml"}
MODULE_SKIP_DIRS = {"frontend", "models", "assets", "docs", "notebooks", "images", "screenshots"}
BHV_FILES = {"index.html", "data/fsa.json", "data/updated.json", "data/backtest.json", "data/accuracy.json"}
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".pytest_cache", "tests", "test"}


def reroot(text: str, prefix: str) -> str:
    for p in ("/static/", "/apps/"):
        text = re.sub(r'(["\'`(])' + re.escape(p), lambda m: m.group(1) + prefix + p, text)
    return text


def main(argv: list[str]) -> int:
    prefix = "/decision-ladder"
    if "--prefix" in argv:
        i = argv.index("--prefix")
        prefix = argv[i + 1].rstrip("/")
        del argv[i:i + 2]
    out = Path(argv[0] if argv else ROOT / "_site").resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    from decision_ladder import __version__
    from decision_ladder import modules as OS
    from decision_ladder.agent import tools as T
    from decision_ladder.engines import ratebook
    from decision_ladder.samples import SAMPLE_BOOK_CSV, SAMPLE_EMAIL, SAMPLES
    from decision_ladder.samples_docs import SAMPLE_DOCS
    from decision_ladder.web.server import Services

    svc = Services(offline=True)
    static_src = ROOT / "decision_ladder" / "web" / "static"
    site = ROOT / "site"

    # ---- web UI
    shutil.copytree(static_src, out / "static")
    for f in (out / "static").rglob("*"):
        if f.is_file() and f.suffix in (".html", ".js", ".css"):
            t = f.read_text(encoding="utf-8")
            if f.name == "styles.css":
                t = t.replace("/static/img/", "img/")
            t = reroot(t, prefix)
            if f.suffix == ".html":
                t = t.replace("<head>", f'<head>\n<script src="{prefix}/static/pages-shim.js"></script>', 1)
            if f.name == "app.js":
                # Renewal Radar's live app refuses to be framed: open it in a new tab instead
                t = t.replace("function openModule(m) {",
                              "function openModule(m) {\n    if (/^https?:/.test(m.ui_url || \"\")) { window.open(m.ui_url, \"_blank\", \"noopener\"); return; }", 1)
            f.write_text(t, encoding="utf-8")
    shim = (site / "pages-shim.js").read_text(encoding="utf-8")
    shim = shim.replace("__PREFIX__", prefix).replace("__PYV__", PYODIDE_VERSION).replace("__RR_LIVE__", RR_LIVE)
    (out / "static" / "pages-shim.js").write_text(shim, encoding="utf-8")
    shutil.copy(out / "static" / "index.html", out / "index.html")

    # ---- browser bridge: FUNCS copied from bridge.mjs, async ESM calls made synchronous
    bridge = (ROOT / "decision_ladder" / "modules" / "bridge.mjs").read_text(encoding="utf-8")
    funcs = bridge[bridge.index("const FUNCS = {"):bridge.index("async function main()")]
    esm = sorted(set(f"{r}/{f}" for r, f in re.findall(r'loadEsm\("([^"]+)",\s*"([^"]+)"\)', funcs)))
    funcs = funcs.replace("async (a) =>", "(a) =>").replace("await loadEsm(", "loadEsm(")
    if "await " in funcs or "async " in funcs:
        raise SystemExit("bridge.mjs has an async pattern the Pages build does not handle")
    head = (site / "pages-bridge.head.js").read_text(encoding="utf-8")
    head = head.replace("__PREFIX__", prefix).replace("__ESM_FILES__", json.dumps(esm))
    (out / "static" / "pages-bridge.js").write_text(head + "  " + funcs + (site / "pages-bridge.tail.js").read_text(encoding="utf-8"),
                                                     encoding="utf-8")
    repos = sorted(set(re.findall(r'(?:load|loadEsm|loadGlobal)\("([^"]+)"', bridge)) | set(re.findall(r'MODS,\s*"([^"]+)"', bridge)))
    for repo in repos:
        src = ROOT / "modules" / repo
        for f in src.rglob("*"):
            if f.is_file() and f.suffix in (".js", ".mjs", ".csv", ".json") and not (SKIP_DIRS & set(f.relative_to(src).parts)) \
                    and f.stat().st_size < BUNDLE_MAX:
                d = out / "modsrc" / repo / f.relative_to(src)
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, d)

    # ---- GET endpoints as JSON snapshots
    cat = OS.catalog()
    for m in cat["modules"]:
        if m["key"] == "renewal-radar":
            m["ui_url"] = RR_LIVE
            m["notes"] = ("FastAPI service: on this static site it opens its own live deployment in a new tab. "
                          "Its engines still run here as tools.")
    health = svc.health()
    health["provider"] = "offline scripted stand-in (no model), running in your browser"
    health["hosting"] = "GitHub Pages static build: Python runs in the browser (Pyodide); no server, no keys"
    api = {
        "health": health,
        "samples": {"files": SAMPLES, "email": SAMPLE_EMAIL, "book_csv": SAMPLE_BOOK_CSV, "documents": SAMPLE_DOCS},
        "os": cat,
        "tools": {"tools": T.specs()},
        "market": ratebook.market_snapshot(),
        "history": {
            "policy_rate": ratebook.history("policy_rate", start="2021-01-01", every=5),
            "goc_5y": ratebook.history("goc_bond_yield", term_months=60, start="2021-01-01", every=5),
            "posted_5y": ratebook.history("big6_typical_posted", term_months=60, start="2021-01-01"),
            "new_uninsured_5y": ratebook.history("actual_rate_new_uninsured", term_months=60, start="2021-01-01"),
        },
    }
    (out / "api").mkdir()
    for k, v in api.items():
        (out / "api" / f"{k}.json").write_text(json.dumps(v, default=str), encoding="utf-8")

    # ---- module apps
    for m in OS.MODULES.values():
        if m.kind != "static" or not m.web_path.is_dir():
            continue
        dest = out / "apps" / m.key
        shutil.copytree(m.web_path, dest, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__"))

    # ---- Python bundle for Pyodide
    (out / "py").mkdir()
    with zipfile.ZipFile(out / "py" / "bundle.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(site / "pyapi.py", "pyapi.py")
        for f in sorted((ROOT / "decision_ladder").rglob("*")):
            rel = f.relative_to(ROOT)
            if f.is_file() and not SKIP_DIRS & set(rel.parts) and rel.parts[1:3] != ("web", "static") \
                    and f.suffix in BUNDLE_EXT and f.stat().st_size < BUNDLE_MAX:
                z.write(f, str(rel))
        for f in sorted((ROOT / "modules").rglob("*")):
            rel = f.relative_to(ROOT)
            if not f.is_file() or SKIP_DIRS & set(rel.parts) or MODULE_SKIP_DIRS & set(rel.parts[2:]):
                continue
            if rel.parts[1] == "benchmark-home-value":   # large app data: only what homevalue.py reads
                if "/".join(rel.parts[2:]) not in BHV_FILES:
                    continue
            elif f.suffix not in MODULE_EXT or f.stat().st_size > BUNDLE_MAX:
                continue
            z.write(f, str(rel))
        z.write(ROOT / "pyproject.toml", "pyproject.toml")

    (out / ".nojekyll").write_text("")
    print(f"built {out} (prefix {prefix}, version {__version__}, {len(list(out.rglob('*')))} files, "
          f"bundle {(out / 'py' / 'bundle.zip').stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

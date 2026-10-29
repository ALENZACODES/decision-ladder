"""Run the full Renewal Radar web app (FastAPI + its own frontend) next to the OS.

Renewal Radar's frontend calls absolute paths (``/api/...``, ``/js/...``, ``/assets/...``), so it must be
served at the root of its own origin. The OS therefore starts it as a separate process on ``RR_PORT``
(default 8100) and links/iframes ``http://<host>:8100/`` instead of proxying it under a path prefix.

    python -m decision_ladder.modules.rr_service        # start in the foreground

Requires Renewal Radar's Python dependencies (``modules/renewal-radar/requirements.txt``: FastAPI,
uvicorn, SQLAlchemy, httpx, PyMuPDF ...). If they are missing, :func:`start` returns a clear error and the
OS keeps running; the in-process Renewal Radar tools (``renewalradar.py``) do not need them.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from .registry import MODULES_DIR

RR_DIR = MODULES_DIR / "renewal-radar"
BACKEND = RR_DIR / "backend"
REQUIRED = ("fastapi", "uvicorn", "sqlalchemy", "httpx", "multipart")

_proc: subprocess.Popen | None = None


def port() -> int:
    return int(os.environ.get("RR_PORT", "8100"))


def base_url() -> str:
    return os.environ.get("RR_PUBLIC_URL") or f"http://127.0.0.1:{port()}"


def missing_dependencies() -> list[str]:
    return [m for m in REQUIRED if importlib.util.find_spec(m) is None]


def command() -> list[str]:
    return [sys.executable, "-m", "uvicorn", "renewal.main:app", "--host", os.environ.get("RR_HOST", "127.0.0.1"),
            "--port", str(port()), "--workers", "1"]


def environment() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env.setdefault("DATABASE_URL", "sqlite:///" + str(Path(tempfile.gettempdir()) / "renewal_radar_os.db"))
    return env


def available(timeout: float = 1.5) -> bool:
    """True when a Renewal Radar server answers /health at base_url()."""
    try:
        with urllib.request.urlopen(base_url() + "/health", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def start(wait: float = 30.0) -> dict:
    """Start the service if it is not already up. Returns a status dict (never raises)."""
    global _proc
    if available():
        return {"ok": True, "url": base_url(), "started": False}
    missing = missing_dependencies()
    if missing:
        return {"ok": False, "url": base_url(), "error": f"Renewal Radar dependencies missing: {', '.join(missing)}. "
                f"Install with: pip install -r {RR_DIR / 'requirements.txt'}"}
    _proc = subprocess.Popen(command(), cwd=str(RR_DIR), env=environment(),
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if _proc.poll() is not None:
            err = (_proc.stderr.read() or b"").decode(errors="replace")[-800:] if _proc.stderr else ""
            return {"ok": False, "url": base_url(), "error": f"Renewal Radar exited (code {_proc.returncode}): {err}"}
        if available(0.5):
            return {"ok": True, "url": base_url(), "started": True, "pid": _proc.pid}
        time.sleep(0.3)
    return {"ok": False, "url": base_url(), "error": f"Renewal Radar did not answer /health within {wait:.0f}s"}


def stop() -> None:
    global _proc
    if _proc is not None and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None


def status() -> dict:
    return {"url": base_url(), "up": available(), "command": " ".join(command()), "cwd": str(RR_DIR),
            "missing_dependencies": missing_dependencies(),
            "note": "Renewal Radar's frontend uses absolute paths, so it runs at the root of its own port."}


if __name__ == "__main__":
    res = start()
    print(res)
    if res.get("ok") and _proc is not None:
        try:
            _proc.wait()
        except KeyboardInterrupt:
            stop()

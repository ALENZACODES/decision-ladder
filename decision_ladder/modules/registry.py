"""Module registry for the Mortgage OS.

Each of the author's existing projects lives under ``modules/<dir>/`` (vendored source) and is registered
here as an :class:`AppModule`: where it sits in the mortgage lifecycle, how its UI is served inside the OS,
and which Nemotron tools it contributes. Integration files (``jsapps.py``, ``homevalue.py``,
``renewalradar.py``) call :func:`add_module` and :func:`add_tool` at import time.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..agent import tools as T

ROOT = Path(__file__).resolve().parent.parent.parent      # repo root
MODULES_DIR = ROOT / "modules"

# Lifecycle stages, in order. Every module belongs to one (or more) stages.
STAGES = [
    ("lead", "Lead & first conversation"),
    ("prequal", "Affordability & pre-qualification"),
    ("documents", "Documents & intake"),
    ("underwriting", "Pre-underwriting & qualification"),
    ("property", "Property value & house prices"),
    ("closing", "Cash to close & closing"),
    ("servicing", "Servicing, renewal & refinance"),
    ("market", "Market, rates & research"),
    ("commercial", "Commercial & private credit"),
]
STAGE_KEYS = [s[0] for s in STAGES]


@dataclass
class AppModule:
    key: str                     # url-safe id, also /apps/<key>/
    name: str
    stages: list[str]
    description: str
    directory: str               # folder under modules/
    entry: str = "index.html"    # UI entry relative to the module's web root
    web_root: str = ""           # sub-folder served at /apps/<key>/ ("" = module root)
    kind: str = "static"         # static | service | data
    repo: str = ""               # ALENZACODES/<repo>
    live_url: str | None = None  # public deployment of the original project, if any
    tools: list[str] = field(default_factory=list)
    lines_of_code: int = 0
    notes: str = ""

    @property
    def path(self) -> Path:
        return MODULES_DIR / self.directory

    @property
    def web_path(self) -> Path:
        return self.path / self.web_root if self.web_root else self.path

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ui_url"] = f"/apps/{self.key}/{self.entry}" if self.kind != "data" else None
        d["present"] = self.path.is_dir()
        return d


MODULES: dict[str, AppModule] = {}


def add_module(m: AppModule) -> AppModule:
    for s in m.stages:
        if s not in STAGE_KEYS:
            raise ValueError(f"unknown stage {s!r} for module {m.key}")
    if not m.lines_of_code:
        m.lines_of_code = count_lines(m.path)
    MODULES[m.key] = m
    return m


def add_tool(tool: T.Tool, module_key: str | None = None) -> T.Tool:
    T.TOOLS[tool.name] = tool
    if module_key and module_key in MODULES and tool.name not in MODULES[module_key].tools:
        MODULES[module_key].tools.append(tool.name)
    return tool


CODE_EXT = {".py", ".js", ".mjs", ".ts", ".html", ".css", ".sql"}


def count_lines(path: Path) -> int:
    if not path.is_dir():
        return 0
    n = 0
    for p in path.rglob("*"):
        if p.suffix in CODE_EXT and p.is_file() and "vendor" not in p.parts and ".min." not in p.name \
                and "node_modules" not in p.parts:
            try:
                n += sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    return n


def catalog() -> dict:
    mods = [m.to_dict() for m in MODULES.values()]
    return {"stages": [{"key": k, "name": n, "modules": [m["key"] for m in mods if k in m["stages"]]} for k, n in STAGES],
            "modules": mods,
            "totals": {"modules": len(mods), "tools": len(T.TOOLS), "module_lines": sum(m["lines_of_code"] for m in mods)}}

"""Mortgage OS modules: the author's existing projects, vendored under modules/ and wired in here."""
from __future__ import annotations

import importlib
import logging

from .registry import MODULES, STAGES, AppModule, add_module, add_tool, catalog  # noqa: F401

INTEGRATIONS = ("core", "jsapps", "homevalue", "renewalradar", "ratedata", "commercial", "business", "disclosure", "servicing", "income")
LOAD_ERRORS: dict[str, str] = {}
_loaded = False


def load_all() -> dict:
    """Import every integration once. A broken integration is recorded, never fatal."""
    global _loaded
    if not _loaded:
        for name in INTEGRATIONS:
            try:
                importlib.import_module(f"{__name__}.{name}")
            except Exception as e:  # noqa: BLE001
                LOAD_ERRORS[name] = f"{type(e).__name__}: {e}"
                logging.getLogger(__name__).warning("module integration %s failed: %s", name, e)
        _loaded = True
    return LOAD_ERRORS

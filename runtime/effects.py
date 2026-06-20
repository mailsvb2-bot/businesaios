from __future__ import annotations

from importlib import import_module
from typing import Any

from runtime.firewall.import_guard import allow_internal_import

CANON_RUNTIME_EFFECTS_IMPORT_SURFACE = True


def load_effects_impl() -> Any:
    with allow_internal_import():
        return import_module(".".join(("runtime", "_internal", "_effects_impl"))).Effects


__all__ = ["CANON_RUNTIME_EFFECTS_IMPORT_SURFACE", "load_effects_impl"]

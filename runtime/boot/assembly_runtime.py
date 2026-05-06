from __future__ import annotations

"""Lightweight compatibility surface for historical runtime assembly imports.

Canonical boot assembly owner: :mod:`runtime.boot.boot_core_assembly`.
This module intentionally does **not** import the canonical owner at module import
because that path may construct a heavy runtime import graph.  Historical callers
can still import the names from here; resolution is lazy and explicit.
"""

from importlib import import_module
from typing import Any

CANON_RUNTIME_BOOT_ASSEMBLY_THIN_ADAPTER = True
CANON_RUNTIME_BOOT_ASSEMBLY_IMPORT_LIGHTWEIGHT = True

__all__ = [
    "CANON_RUNTIME_BOOT_ASSEMBLY_THIN_ADAPTER",
    "CANON_RUNTIME_BOOT_ASSEMBLY_IMPORT_LIGHTWEIGHT",
    "CANON_BOOT_WIRING_ONLY",
    "CoreAssembly",
    "build_core_assembly",
    "build_decision_core",
    "build_reward_and_learning_components",
    "build_survival_and_economics",
]

def _owner() -> Any:
    return import_module("runtime.boot.boot_core_assembly")

def __getattr__(name: str) -> Any:
    if name in __all__:
        return getattr(_owner(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

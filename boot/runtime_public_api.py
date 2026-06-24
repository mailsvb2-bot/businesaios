from __future__ import annotations

"""Transition public API for runtime assembly.
This module remains a lazy bridge and must not become a second runtime owner.
Runtime assembly delegates to the canonical package-level bootstrap owner in
``bootstrap.compose`` while preserving the runtime bootstrap ABI.
"""

from importlib import import_module
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.bootstrap import BuiltRuntime

CANON_RUNTIME_BOOT_PUBLIC_API = True
CANON_LEGACY_BOOTSTRAP_SHIM = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.compose"
CANON_RUNTIME_PUBLIC_API_DELEGATES_TO_SOVEREIGN_BOOTSTRAP = True
CANON_RUNTIME_PUBLIC_API_NO_RUNTIME_ORCHESTRATOR_IMPORT = True
CANON_RUNTIME_PUBLIC_API_DIRECT_OWNER_BOOTSTRAP = True
CANON_RUNTIME_PUBLIC_API_DIRECT_RUNTIME_TYPE_EXPORT = True
CANON_RUNTIME_PUBLIC_API_BOOTSTRAP_COMPOSE_OWNER = True

__all__ = [
    "CANON_RUNTIME_BOOT_PUBLIC_API",
    "CANON_LEGACY_BOOTSTRAP_SHIM",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "CANON_RUNTIME_PUBLIC_API_DELEGATES_TO_SOVEREIGN_BOOTSTRAP",
    "CANON_RUNTIME_PUBLIC_API_NO_RUNTIME_ORCHESTRATOR_IMPORT",
    "CANON_RUNTIME_PUBLIC_API_DIRECT_OWNER_BOOTSTRAP",
    "CANON_RUNTIME_PUBLIC_API_DIRECT_RUNTIME_TYPE_EXPORT",
    "CANON_RUNTIME_PUBLIC_API_BOOTSTRAP_COMPOSE_OWNER",
    "BuiltRuntime",
    "build_runtime",
]


def _bootstrap_runtime_owner():
    return getattr(import_module("bootstrap.compose"), "bootstrap_runtime")


def _built_runtime_type():
    return getattr(import_module("runtime.bootstrap"), "BuiltRuntime")


def build_runtime(*args: Any, **kwargs: Any):
    project_root = kwargs.pop("project_root", None)
    if args:
        raise TypeError("build_runtime accepts keyword-only usage")
    if kwargs:
        raise TypeError(f"unexpected keyword arguments: {sorted(kwargs)}")
    return getattr(import_module("bootstrap.compose"), "build_runtime")(project_root=project_root)


def __getattr__(name: str):
    if name == "BuiltRuntime":
        return _built_runtime_type()
    raise AttributeError(name)

from __future__ import annotations

from importlib import import_module

from runtime.registry import RuntimeRegistry

CANON_RUNTIME_SOVEREIGN_BOOT_WRAPPER = True
CANON_COMPAT_SHIM = True
CANON_NO_ROOT_ASSEMBLY_LOGIC = True


def _load_sovereign_bootstrap_runtime():
    return import_module("runtime.bootstrap.sovereign_bootstrap").bootstrap_runtime


def boot_runtime() -> RuntimeRegistry:
    return _load_sovereign_bootstrap_runtime()().artifacts.registry


__all__ = [
    "CANON_COMPAT_SHIM",
    "CANON_NO_ROOT_ASSEMBLY_LOGIC",
    "CANON_RUNTIME_SOVEREIGN_BOOT_WRAPPER",
    "boot_runtime",
]

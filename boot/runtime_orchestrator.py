from __future__ import annotations

"""Legacy internal shim for the canonical runtime builder.

This module must not own runtime assembly. The canonical public owner lives in
``bootstrap.compose`` and the canonical concrete runtime builder lives in
``runtime.bootstrap.runtime_builder``. Only narrow compatibility access is kept
here for legacy internal callers.
"""

from importlib import import_module
from typing import Any

from runtime.bootstrap.runtime_builder import RuntimeBuilder

CANON_RUNTIME_ASSEMBLY_INTERNAL_ONLY = True
CANON_RUNTIME_ASSEMBLY_NO_PUBLIC_BOOTSTRAP = True
CANON_RUNTIME_ASSEMBLY_THIN_SHIM = True
CANON_RUNTIME_ASSEMBLY_DELEGATES_TO_RUNTIME_BUILDER = True
CANON_RUNTIME_ASSEMBLY_NO_DIRECT_OWNER_EXPORTS = True
CANON_RUNTIME_ASSEMBLY_PUBLIC_OWNER_IS_BOOTSTRAP_COMPOSE = True

RuntimeOrchestrator = RuntimeBuilder


def build_runtime(*, project_root: str | None = None):
    return getattr(import_module("bootstrap.compose"), "build_runtime")(project_root=project_root)


def __getattr__(name: str) -> Any:
    if name in {
        "BuiltRuntime",
        "RuntimeBuilder",
        "build_runtime",
    }:
        from runtime.bootstrap.runtime_builder import BuiltRuntime, RuntimeBuilder as _RuntimeBuilder

        mapping = {
            "BuiltRuntime": BuiltRuntime,
            "RuntimeBuilder": _RuntimeBuilder,
            "build_runtime": build_runtime,
        }
        return mapping[name]
    raise AttributeError(name)


__all__ = [
    "CANON_RUNTIME_ASSEMBLY_INTERNAL_ONLY",
    "CANON_RUNTIME_ASSEMBLY_NO_PUBLIC_BOOTSTRAP",
    "CANON_RUNTIME_ASSEMBLY_THIN_SHIM",
    "CANON_RUNTIME_ASSEMBLY_DELEGATES_TO_RUNTIME_BUILDER",
    "CANON_RUNTIME_ASSEMBLY_NO_DIRECT_OWNER_EXPORTS",
    "CANON_RUNTIME_ASSEMBLY_PUBLIC_OWNER_IS_BOOTSTRAP_COMPOSE",
    "RuntimeOrchestrator",
    "build_runtime",
]

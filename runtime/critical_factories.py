from __future__ import annotations

"""Lazy external shim for critical runtime factory builders.

This root module must not become a factory owner or force eager import of
boot-time construction graph during runtime namespace import. The canonical
construction logic lives under the ``boot.factories`` package owner surface and is loaded on demand.
"""

from importlib import import_module
from typing import Any

CANON_COMPAT_SHIM = True
CANON_NO_ROOT_FACTORY_OWNERSHIP = True
CANON_LAZY_IMPORT_SHIM = True
CANON_CRITICAL_FACTORIES_PACKAGE_OWNER = "boot.factories"

_EXPORT_SPECS = {
    "build_action_executor": ("boot.factories", "build_action_executor"),
    "build_decision_core": ("boot.factories", "build_decision_core"),
    "build_runtime_decision_execution_service": ("boot.factories", "build_runtime_decision_execution_service"),
    "build_governance_chain": ("boot.factories", "build_governance_chain"),
}


def __getattr__(name: str) -> Any:
    spec = _EXPORT_SPECS.get(name)
    if spec is None:
        raise AttributeError(name)
    module_name, attr_name = spec
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_EXPORT_SPECS.keys()))


__all__ = [
    "CANON_COMPAT_SHIM",
    "CANON_LAZY_IMPORT_SHIM",
    "CANON_CRITICAL_FACTORIES_PACKAGE_OWNER",
    "CANON_NO_ROOT_FACTORY_OWNERSHIP",
    *sorted(_EXPORT_SPECS.keys()),
]

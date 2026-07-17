"""Canonical action owner surface with cycle-safe lazy exports.

The package root is the supported owner surface for action catalog construction.
All submodule exports are resolved lazily so low-level boot catalog modules can
import ``core.actions.names`` without recursively initializing the runtime action
registry. Historical imports remain compatible and no duplicate action data is
stored here.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

CANON_CORE_ACTIONS_OWNER = True

_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "ACTION_ADS_APPLY_EXECUTE_V1": (
        "core.actions.names",
        "ACTION_ADS_APPLY_EXECUTE_V1",
    ),
    "ACTION_AI_CEO_PLAN_V1": (
        "core.actions.names",
        "ACTION_AI_CEO_PLAN_V1",
    ),
    "ACTION_EXECUTE_PLAN_V1": (
        "core.actions.names",
        "ACTION_EXECUTE_PLAN_V1",
    ),
    "ACTION_ROUTE_LEAD_V1": (
        "core.actions.names",
        "ACTION_ROUTE_LEAD_V1",
    ),
    "ACTION_PROOF_EVENT": (
        "core.actions.proof_registry",
        "ACTION_PROOF_EVENT",
    ),
    "ALLOWED_ACTIONS": (
        "core.actions.allowed_actions",
        "ALLOWED_ACTIONS",
    ),
    "ActionSchemaRegistry": (
        "core.actions.schema_registry",
        "ActionSchemaRegistry",
    ),
    "CatalogEntry": (
        "core.actions.catalog_entry",
        "CatalogEntry",
    ),
    "build_catalog": (
        "core.actions.catalog",
        "build_catalog",
    ),
    "build_catalog_groups": (
        "core.actions.catalog_groups",
        "build_catalog_groups",
    ),
    "build_default_registry": (
        "core.actions.schema_registry",
        "build_default_registry",
    ),
    "build_schema_registry": (
        "core.actions.catalog",
        "build_schema_registry",
    ),
}


def _resolve_export(name: str) -> Any:
    module_name, attribute_name = _EXPORT_MAP[name]
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __getattr__(name: str) -> Any:
    if name in _EXPORT_MAP:
        return _resolve_export(name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "ACTION_ADS_APPLY_EXECUTE_V1",
    "ACTION_AI_CEO_PLAN_V1",
    "ACTION_EXECUTE_PLAN_V1",
    "ACTION_ROUTE_LEAD_V1",
    "ACTION_PROOF_EVENT",
    "ALLOWED_ACTIONS",
    "ActionSchemaRegistry",
    "CANON_CORE_ACTIONS_OWNER",
    "CatalogEntry",
    "build_catalog",
    "build_catalog_groups",
    "build_default_registry",
    "build_schema_registry",
]

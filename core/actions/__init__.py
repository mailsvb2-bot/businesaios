"""Canonical action owner surface.

The package root is the supported owner surface for action catalog
construction. Historical ``core.actions.catalog`` imports remain valid, but
internal code should import from ``core.actions`` so catalog implementation
files stop behaving like a second public surface.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from core.actions.allowed_actions import ALLOWED_ACTIONS
from core.actions.catalog_entry import CatalogEntry
from core.actions.catalog_groups import build_catalog_groups
from core.actions.names import (
    ACTION_ADS_APPLY_EXECUTE_V1,
    ACTION_AI_CEO_PLAN_V1,
    ACTION_EXECUTE_PLAN_V1,
)
from core.actions.proof_registry import ACTION_PROOF_EVENT
from core.actions.schema_registry import ActionSchemaRegistry, build_default_registry

CANON_CORE_ACTIONS_OWNER = True
_OWNER_MODULE = 'core.actions.catalog'
_OWNER_EXPORTS = ['build_catalog', 'build_schema_registry']

def _owner() -> Any:
    return import_module(_OWNER_MODULE)


def __getattr__(name: str) -> Any:
    if name == 'CANON_CORE_ACTIONS_OWNER':
        return CANON_CORE_ACTIONS_OWNER
    if name in _OWNER_EXPORTS:
        return getattr(_owner(), name)
    raise AttributeError(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(_OWNER_EXPORTS))


__all__ = [
    'ACTION_ADS_APPLY_EXECUTE_V1',
    'ACTION_AI_CEO_PLAN_V1',
    'ACTION_EXECUTE_PLAN_V1',
    'ACTION_PROOF_EVENT',
    'ALLOWED_ACTIONS',
    'ActionSchemaRegistry',
    'CANON_CORE_ACTIONS_OWNER',
    'CatalogEntry',
    'build_catalog',
    'build_catalog_groups',
    'build_default_registry',
    'build_schema_registry',
]

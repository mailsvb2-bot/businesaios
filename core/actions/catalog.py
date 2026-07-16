"""Action schema catalog bound to the canonical runtime action registry.

Runtime Action Registry owns executable action names. This module owns payload
schema details only; it cannot advertise a second set of actions.
"""

from __future__ import annotations

from core.actions.allowed_actions import ALLOWED_ACTIONS
from core.ai.schema_registry import DecisionSchema, SchemaRegistry

from .catalog_entry import CatalogEntry
from .catalog_groups import build_catalog_groups


def _generic_compat_entry(action: str) -> CatalogEntry:
    return CatalogEntry(
        action=str(action),
        version=1,
        schema=DecisionSchema(
            required=set(),
            optional=set(),
            field_types={},
            allow_additional=True,
        ),
    )


def build_catalog() -> dict[str, CatalogEntry]:
    declared: dict[str, CatalogEntry] = {}
    for group in build_catalog_groups():
        overlap = set(declared) & set(group)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"duplicate catalog actions: {names}")
        declared.update(group)

    active_actions = {str(action) for action in ALLOWED_ACTIONS}
    return {
        action: declared.get(action) or _generic_compat_entry(action)
        for action in sorted(active_actions)
    }


def build_schema_registry() -> SchemaRegistry:
    reg = SchemaRegistry()
    for entry in build_catalog().values():
        reg.register(entry.action, entry.version, entry.schema)
    return reg

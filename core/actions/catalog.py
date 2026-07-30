"""Public action-schema catalog adapter bound to the runtime registry."""

from __future__ import annotations

from core.actions.allowed_actions import ALLOWED_ACTIONS
from core.ai.schema_registry import SchemaRegistry

from .catalog_builder import build_catalog as _build_catalog
from .catalog_entry import CatalogEntry
from .catalog_groups import build_catalog_groups


def build_catalog() -> dict[str, CatalogEntry]:
    return _build_catalog(group_builder=build_catalog_groups, allowed_actions=ALLOWED_ACTIONS)


def build_schema_registry() -> SchemaRegistry:
    schema_registry = SchemaRegistry()
    for entry in build_catalog().values():
        schema_registry.register(entry.action, entry.version, entry.schema)
    return schema_registry


__all__ = ["ALLOWED_ACTIONS", "build_catalog", "build_schema_registry"]

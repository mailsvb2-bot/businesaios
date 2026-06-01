"""Action Catalog (single source of truth).

The catalog stays canonical, but the entry definitions live in small grouped
modules so the contract is easier to audit and extend without growing another
God module.
"""

from __future__ import annotations

from core.ai.schema_registry import SchemaRegistry

from .catalog_entry import CatalogEntry
from .catalog_groups import build_catalog_groups


def build_catalog() -> dict[str, CatalogEntry]:
    catalog: dict[str, CatalogEntry] = {}
    for group in build_catalog_groups():
        overlap = set(catalog) & set(group)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"duplicate catalog actions: {names}")
        catalog.update(group)
    return catalog


def build_schema_registry() -> SchemaRegistry:
    reg = SchemaRegistry()
    for entry in build_catalog().values():
        reg.register(entry.action, entry.version, entry.schema)
    return reg

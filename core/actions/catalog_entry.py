from __future__ import annotations

from dataclasses import dataclass

from core.ai.schema_registry import DecisionSchema


@dataclass(frozen=True)
class CatalogEntry:
    action: str
    version: int
    schema: DecisionSchema


__all__ = ["CatalogEntry"]

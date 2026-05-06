from __future__ import annotations

from collections.abc import Callable
from typing import Any


class MigrationRegistry:
    def __init__(self) -> None:
        self._migrations: dict[tuple[str, str], Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(
        self,
        from_version: str,
        to_version: str,
        migration: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        self._migrations[(from_version, to_version)] = migration

    def get(self, from_version: str, to_version: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
        return self._migrations[(from_version, to_version)]

__all__ = [
    "MigrationRegistry",
]

from __future__ import annotations

from collections.abc import Iterable, MutableMapping
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class PolicyRegistryStore(Generic[T]):
    """Minimal local registry for concrete policy objects.

    This store is intentionally scoped to ``core.ai`` so the canonical
    DecisionCore policy path does not depend on the wider shared registry
    namespace. It keeps the active object map local while lifecycle state
    remains owned by ``core.policies``.
    """

    namespace: str = "policies"
    _items: MutableMapping[str, T] = field(default_factory=dict)

    def replace(self, key: str, value: T) -> None:
        self._items[self._normalize(key)] = value

    def get(self, key: str) -> T:
        normalized = self._normalize(key)
        if normalized not in self._items:
            raise KeyError(f"unknown registry key in {self.namespace}: {normalized}")
        return self._items[normalized]

    def maybe_get(self, key: str) -> T | None:
        normalized = str(key).strip()
        if not normalized:
            return None
        return self._items.get(normalized)

    def keys(self) -> Iterable[str]:
        return tuple(self._items.keys())

    def _normalize(self, key: str) -> str:
        normalized = str(key).strip()
        if not normalized:
            raise ValueError(f"empty registry key in {self.namespace}")
        return normalized

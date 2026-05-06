from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Iterable, MutableMapping, TypeVar

T = TypeVar("T")


@dataclass
class InputRegistry(Generic[T]):
    """Local canonical registry for decision input builders.

    Keeps decision-input registration inside the core contour so callers do not
    depend on the generic shared registry namespace.
    """

    namespace: str = "decision_inputs"
    _items: MutableMapping[str, T] = field(default_factory=dict)

    def register(self, key: str, value: T) -> None:
        normalized = self._normalize(key)
        if normalized in self._items:
            raise ValueError(f"duplicate registry key in {self.namespace}: {normalized}")
        self._items[normalized] = value

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

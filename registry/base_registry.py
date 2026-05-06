from __future__ import annotations

"""Compatibility registry surface backed by the canonical shared registry core.

This module preserves the historical BaseRegistry API used across multiple
feature namespaces, while delegating storage/invariant primitives to the single
shared registry implementation.
"""

from shared.registry import Registry as _CanonicalRegistry

CANON_REGISTRY_BASE_ON_SHARED = True


class BaseRegistry:
    def __init__(self, *, kind: str = "item") -> None:
        self._kind = str(kind)
        self._items = _CanonicalRegistry[object](namespace=self._kind)

    def register(self, name: str, item: object) -> None:
        key = str(name).strip()
        if not key:
            raise ValueError(f"{self._kind} name must be non-empty")
        # Historical BaseRegistry semantics are replace-on-register.
        self._items.replace(key, item)

    def register_unique(self, name: str, item: object, *, error_prefix: str | None = None) -> None:
        key = str(name).strip()
        if not key:
            raise ValueError(f"{self._kind} name must be non-empty")
        if key in self._items:
            label = error_prefix or self._kind
            raise ValueError(f"duplicate {label}: {key}")
        self._items.register(key, item)

    def get(self, name: str) -> object:
        key = str(name).strip()
        if not key:
            raise KeyError(key)
        return self._items.get(key)

    def require(self, name: str) -> object:
        return self.get(name)

    def maybe_get(self, name: str) -> object | None:
        key = str(name).strip()
        if not key:
            return None
        return self._items.maybe_get(key)

    def snapshot(self) -> dict[str, object]:
        return dict(self._items.items())

    def items(self) -> tuple[tuple[str, object], ...]:
        return tuple(sorted(self._items.items()))

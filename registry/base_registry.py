from __future__ import annotations

"""Compatibility registry surface backed by one storage owner.

Default construction keeps the historical in-memory behavior used by pure domain
unit tests. Runtime owners may inject a durable backend implementing the same
replace/register/get/items contract; the registry remains the only public API.
"""

from typing import Protocol

from shared.registry import Registry as _CanonicalRegistry

CANON_REGISTRY_BASE_ON_SHARED = True
CANON_REGISTRY_DURABLE_BACKEND_INJECTION = True


class RegistryBackend(Protocol):
    def replace(self, key: str, value: object) -> None: ...
    def register_unique(self, key: str, value: object) -> None: ...
    def get(self, key: str) -> object: ...
    def maybe_get(self, key: str) -> object | None: ...
    def items(self) -> tuple[tuple[str, object], ...]: ...


class BaseRegistry:
    def __init__(self, *, kind: str = 'item', backend: RegistryBackend | None = None) -> None:
        self._kind = str(kind)
        self._backend = backend
        self._items = None if backend is not None else _CanonicalRegistry[object](namespace=self._kind)

    def register(self, name: str, item: object) -> None:
        key = str(name).strip()
        if not key:
            raise ValueError(f'{self._kind} name must be non-empty')
        if self._backend is not None:
            self._backend.replace(key, item)
            return
        assert self._items is not None
        self._items.replace(key, item)

    def register_unique(self, name: str, item: object, *, error_prefix: str | None = None) -> None:
        key = str(name).strip()
        if not key:
            raise ValueError(f'{self._kind} name must be non-empty')
        if self._backend is not None:
            try:
                self._backend.register_unique(key, item)
            except ValueError as exc:
                label = error_prefix or self._kind
                raise ValueError(f'duplicate {label}: {key}') from exc
            return
        assert self._items is not None
        if key in self._items:
            label = error_prefix or self._kind
            raise ValueError(f'duplicate {label}: {key}')
        self._items.register(key, item)

    def get(self, name: str) -> object:
        key = str(name).strip()
        if not key:
            raise KeyError(key)
        if self._backend is not None:
            return self._backend.get(key)
        assert self._items is not None
        return self._items.get(key)

    def require(self, name: str) -> object:
        return self.get(name)

    def maybe_get(self, name: str) -> object | None:
        key = str(name).strip()
        if not key:
            return None
        if self._backend is not None:
            return self._backend.maybe_get(key)
        assert self._items is not None
        return self._items.maybe_get(key)

    def snapshot(self) -> dict[str, object]:
        return dict(self.items())

    def items(self) -> tuple[tuple[str, object], ...]:
        if self._backend is not None:
            return tuple(sorted(self._backend.items()))
        assert self._items is not None
        return tuple(sorted(self._items.items()))


__all__ = [
    'BaseRegistry',
    'CANON_REGISTRY_BASE_ON_SHARED',
    'CANON_REGISTRY_DURABLE_BACKEND_INJECTION',
    'RegistryBackend',
]

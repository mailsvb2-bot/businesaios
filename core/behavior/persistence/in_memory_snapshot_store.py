from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


class InMemorySnapshotStore(Generic[T]):
    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def put(self, key: str, value: T) -> None:
        self._items[key] = value

    def get(self, key: str) -> T | None:
        return self._items.get(key)

    def list_keys(self) -> list[str]:
        return list(self._items.keys())

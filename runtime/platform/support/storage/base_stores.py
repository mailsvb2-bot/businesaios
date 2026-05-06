from __future__ import annotations

class ArtifactStore:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def put(self, key: str, value: object) -> None:
        self._items[key] = value

    def get(self, key: str) -> object:
        return self._items[key]


class DatasetStore:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def put(self, key: str, value: object) -> None:
        self._items[key] = value

    def get(self, key: str) -> object:
        return self._items[key]

__all__ = [
    "ArtifactStore",
    "DatasetStore",
]

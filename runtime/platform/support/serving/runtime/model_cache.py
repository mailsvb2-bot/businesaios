from __future__ import annotations


class ModelCache:
    def __init__(self) -> None:
        self._cache: dict[str, object] = {}

    def get(self, key: str):
        return self._cache.get(key)

    def put(self, key: str, value: object) -> None:
        self._cache[key] = value

__all__ = ["ModelCache"]

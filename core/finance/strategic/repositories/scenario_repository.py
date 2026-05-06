from __future__ import annotations


class ScenarioRepository:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def save(self, key: str, value: object) -> None:
        self._items[key] = value

    def get(self, key: str):
        return self._items.get(key)

    def all(self) -> dict[str, object]:
        return dict(self._items)

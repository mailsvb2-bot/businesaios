from __future__ import annotations


class SchemaRegistry:
    def __init__(self) -> None:
        self._schemas: dict[str, dict] = {}

    def register(self, name: str, schema: dict) -> None:
        self._schemas[name] = dict(schema)

    def get(self, name: str) -> dict:
        return dict(self._schemas[name])

__all__ = [
    "SchemaRegistry",
]

from __future__ import annotations


class SchemaVersioning:
    def __init__(self) -> None:
        self._versions: dict[str, int] = {}

    def next(self, name: str) -> str:
        self._versions[name] = self._versions.get(name, 0) + 1
        return str(self._versions[name])

__all__ = [
    "SchemaVersioning",
]

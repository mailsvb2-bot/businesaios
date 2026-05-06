from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


class SQLAdapter:
    """Tiny sqlite-backed adapter for local support queries."""

    PLATFORM_SUPPORT_LOCAL = True

    def __init__(self, dsn: str = ":memory:") -> None:
        import importlib

        sqlite = importlib.import_module("sqlite3")
        self._connection = sqlite.connect(dsn)
        self._connection.row_factory = sqlite.Row

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> Any:
        cursor = self._connection.execute(str(query), tuple(parameters))
        if cursor.description is None:
            self._connection.commit()
            return cursor.rowcount
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


class TracingAdapter:
    """Append-only local trace sink."""

    PLATFORM_SUPPORT_LOCAL = True

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def record(self, name: str, payload: Mapping[str, Any]) -> None:
        event = {"name": str(name), "payload": deepcopy(dict(payload))}
        self._events.append(event)

    def events(self) -> list[dict[str, Any]]:
        return [{"name": item["name"], "payload": deepcopy(dict(item["payload"]))} for item in self._events]

__all__ = [
    "SQLAdapter",
    "TracingAdapter",
]

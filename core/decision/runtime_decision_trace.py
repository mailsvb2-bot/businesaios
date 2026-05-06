from __future__ import annotations

from typing import Any


class RuntimeDecisionTrace:
    """Canonical core-owned compat trace buffer for runtime explainability paths."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def add(self, event: dict[str, Any]) -> None:
        self._events.append(dict(event))

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)


DecisionTrace = RuntimeDecisionTrace

__all__ = ["DecisionTrace", "RuntimeDecisionTrace"]

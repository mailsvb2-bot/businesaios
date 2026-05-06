from __future__ import annotations

from typing import Any

from observability.demand._emitter import emit_event


class DemandEventEmitter:
    """Thin typed emitter that keeps event semantics centralized.

    Modules at the boundary should only declare *which* event stream they belong
    to; payload emission stays in one place so the wrapper files do not grow
    their own semantics over time.
    """

    def __init__(self, event_type: str) -> None:
        normalized = str(event_type).strip()
        if not normalized:
            raise ValueError('event_type must be non-empty')
        self._event_type = normalized

    def emit(self, event_log: Any, event_name: str, payload: dict[str, object]) -> None:
        emit_event(event_log, event_type=self._event_type, event_name=event_name, payload=payload)


def emit_typed(event_type: str, event_log: Any, event_name: str, payload: dict[str, object]) -> None:
    DemandEventEmitter(event_type).emit(event_log, event_name, payload)

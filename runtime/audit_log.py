"""Small in-memory audit log used by runtime observability.

The project treats runtime observability as a first-class dependency.  This
module intentionally exposes a tiny, deterministic API rather than a fake
production logger so tests and boot wiring can rely on one canonical audit
surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


class RuntimeAuditLog:
    """Simple append-only audit event buffer.

    It is deliberately synchronous and in-memory: the purpose is to preserve
    a single contract for runtime auditability during boot, tests, replay, and
    local execution.  External sinks can subscribe elsewhere without changing
    this API.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, name: str, /, **payload: Any) -> None:
        self._events.append(AuditEvent(name=name, payload=dict(payload)))

    def records(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def event_names(self) -> tuple[str, ...]:
        return tuple(event.name for event in self._events)

    def latest(self) -> AuditEvent | None:
        return self._events[-1] if self._events else None

    def clear(self) -> None:
        self._events.clear()

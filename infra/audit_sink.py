from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from infra.audit_event import AuditEvent


class AuditSink:
    def append(self, event: AuditEvent) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def events(self) -> tuple[AuditEvent, ...]:  # pragma: no cover - interface
        raise NotImplementedError

    def append_many(self, events: Iterable[AuditEvent]) -> None:
        for event in events:
            self.append(event)

    def snapshot(self) -> tuple[AuditEvent, ...]:
        return self.events()


@dataclass
class InMemoryAuditSink(AuditSink):
    _events: list[AuditEvent] = field(default_factory=list)

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

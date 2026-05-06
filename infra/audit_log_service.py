from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infra.audit_event import AuditEvent
from infra.audit_sink import AuditSink


@dataclass(frozen=True)
class AuditLogService:
    sink: AuditSink

    def record(
        self,
        *,
        event_name: str,
        actor: str,
        category: str,
        payload: dict[str, Any],
    ) -> AuditEvent:
        event = AuditEvent(
            event_name=event_name,
            actor=actor,
            category=category,
            payload=dict(payload),
        )
        self.sink.append(event)
        return event

    def events(self) -> tuple[AuditEvent, ...]:
        return self.sink.events()

from __future__ import annotations

from observability.crm.crm_audit_event_schema import CrmAuditEvent


class CrmActionAuditLog:
    def __init__(self) -> None:
        self.events: list[CrmAuditEvent] = []

    def append(self, event: CrmAuditEvent) -> None:
        self.events.append(event)

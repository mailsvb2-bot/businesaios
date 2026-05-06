from __future__ import annotations

from dataclasses import dataclass, field

from infra.audit_log_service import AuditLogService
from infra.change_request import ChangeRequest


@dataclass
class ChangeManagementService:
    audit_log: AuditLogService
    _changes: list[ChangeRequest] = field(default_factory=list)

    def apply(self, request: ChangeRequest) -> None:
        self._changes.append(request)
        self.audit_log.record(
            event_name="change_applied",
            actor=request.actor,
            category="change_management",
            payload={
                "change_id": request.change_id,
                "change_type": request.change_type,
                "target_name": request.target_name,
                "payload": dict(request.payload),
            },
        )

    def list_changes(self) -> tuple[ChangeRequest, ...]:
        return tuple(self._changes)

from __future__ import annotations

from dataclasses import dataclass

from infra.approval_request import ApprovalRequest
from infra.approval_store import InMemoryApprovalStore
from infra.audit_log_service import AuditLogService


@dataclass(frozen=True)
class ApprovalService:
    store: InMemoryApprovalStore
    audit_log: AuditLogService

    def submit(self, request: ApprovalRequest) -> None:
        self.store.put(request)
        self.audit_log.record(
            event_name="approval_request_submitted",
            actor=request.actor,
            category="approval",
            payload={
                "request_id": request.request_id,
                "approval_type": request.approval_type,
                "target_name": request.target_name,
                "required_steps": list(request.required_steps),
            },
        )

    def approve_step(
        self,
        *,
        actor: str,
        request_id: str,
        step_name: str,
    ) -> None:
        request = self.store.get(request_id)
        if step_name not in request.required_steps:
            raise ValueError(
                f"Illegal approval step '{step_name}' for request '{request_id}'."
            )

        self.store.approve_step(request_id, step_name)
        self.audit_log.record(
            event_name="approval_step_approved",
            actor=actor,
            category="approval",
            payload={
                "request_id": request_id,
                "step_name": step_name,
            },
        )

    def is_fully_approved(self, request_id: str) -> bool:
        request = self.store.get(request_id)
        approved = set(self.store.approved_steps(request_id))
        required = set(request.required_steps)
        return required.issubset(approved)

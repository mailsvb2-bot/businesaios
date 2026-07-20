from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from governance.approval_audit import build_approval_decision_audit, build_approval_requested_audit
from governance.approval_contract import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRecord,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStoreContract,
    utc_now,
)
from governance.control_plane_audit_log import GovernanceAuditEvent, GovernanceAuditLogContract, NullGovernanceAuditLog
from governance.rbac_contract import RoleId
from governance.role_catalog import RoleCatalog

CANON_GOVERNANCE_APPROVAL_WORKFLOW = True


class ApprovalWorkflow:
    """
    Explicit approval lifecycle.

    Enterprise properties:
    - tenant-bound
    - subject-bound
    - fail-closed
    - no self-approval by default
    - no duplicate decisions from same actor
    - role-group satisfaction enforced
    - same actor cannot satisfy multiple required groups in dual-control flows
    """

    def __init__(
        self,
        *,
        store: ApprovalStoreContract,
        role_catalog: RoleCatalog | None = None,
        audit_log: GovernanceAuditLogContract | None = None,
    ) -> None:
        self._store = store
        self._role_catalog = role_catalog or RoleCatalog()
        self._audit_log = audit_log or NullGovernanceAuditLog()

    def submit(self, request: ApprovalRequest) -> ApprovalRecord:
        request.validate()
        record = self._store.create(request)
        self._emit_audit(build_approval_requested_audit(record))
        return record

    def get(self, approval_id: str) -> ApprovalRecord | None:
        return self._store.get(approval_id)

    def evaluate(self, decision: ApprovalDecision) -> ApprovalRecord:
        decision.validate()
        record = self._store.get(decision.approval_id)
        if record is None:
            raise ValueError(f"approval not found: {decision.approval_id}")
        if record.is_terminal:
            if record.status is ApprovalStatus.EXPIRED:
                return record
            raise RuntimeError(f"approval already terminal: {record.request.approval_id}")

        request = record.request

        if decision.tenant_id != request.tenant_id:
            raise RuntimeError("cross-tenant approval decision is forbidden")

        if request.expires_at is not None and utc_now() > request.expires_at:
            expired = replace(record, status=ApprovalStatus.EXPIRED, final_reason="expired")
            saved = self._store.save(expired)
            self._emit_audit({
                "event_type": "approval_expired",
                "tenant_id": request.tenant_id,
                "approval_id": request.approval_id,
                "subject_type": request.subject_type,
                "subject_id": request.subject_id,
                "status_after": saved.status.value,
            })
            return saved

        if request.prohibit_self_approval and decision.actor_id == request.requested_by:
            raise RuntimeError("self_approval_is_forbidden")

        if any(item.actor_id == decision.actor_id for item in record.decisions):
            raise RuntimeError("duplicate_approval_decision_from_same_actor")

        if request.required_role_groups and not self._role_allowed_for_request(
            decision.role_id,
            request.required_role_groups,
        ):
            raise RuntimeError("decision_role_not_authorized_for_request")

        if not self._role_catalog.is_human_approver_role(decision.role_id):
            raise RuntimeError("non_human_approver_role_forbidden")

        next_decisions = tuple(record.decisions) + (decision,)

        if decision.outcome is ApprovalOutcome.REJECT:
            rejected = replace(
                record,
                decisions=next_decisions,
                status=ApprovalStatus.REJECTED,
                final_reason="rejected_by_authorized_actor",
            )
            saved = self._store.save(rejected)
            self._emit_audit(build_approval_decision_audit(record=saved, decision=decision))
            return saved

        approved = self._is_request_fully_approved(
            request=request,
            decisions=next_decisions,
        )
        next_status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REQUESTED
        next_reason = "approval_requirements_satisfied" if approved else None
        updated = replace(
            record,
            decisions=next_decisions,
            status=next_status,
            final_reason=next_reason,
        )
        saved = self._store.save(updated)
        self._emit_audit(build_approval_decision_audit(record=saved, decision=decision))
        return saved
    resolve = evaluate

    def _emit_audit(self, payload: dict[str, object]) -> None:
        tenant_id = str(payload.get("tenant_id") or "")
        self._audit_log.append(
            GovernanceAuditEvent(
                event_type=str(payload.get("event_type") or "governance_event"),
                tenant_id=tenant_id,
                emitted_at=datetime.now(UTC),
                payload=payload,
            )
        )

    def is_approved(self, approval_id: str) -> bool:
        record = self._store.get(approval_id)
        return bool(record is not None and record.status is ApprovalStatus.APPROVED)

    @staticmethod
    def _role_allowed_for_request(
        role_id: RoleId,
        role_groups: tuple[tuple[RoleId, ...], ...],
    ) -> bool:
        return any(role_id in group for group in role_groups)

    @staticmethod
    def _is_request_fully_approved(
        *,
        request: ApprovalRequest,
        decisions: tuple[ApprovalDecision, ...],
    ) -> bool:
        approving_decisions = tuple(
            decision
            for decision in decisions
            if decision.outcome is ApprovalOutcome.APPROVE
        )
        distinct_actors = {decision.actor_id for decision in approving_decisions}
        if len(distinct_actors) < request.min_distinct_approvers:
            return False

        if not request.required_role_groups:
            return True

        used_actors: set[str] = set()
        for role_group in request.required_role_groups:
            matched = next(
                (
                    decision
                    for decision in approving_decisions
                    if decision.role_id in role_group and decision.actor_id not in used_actors
                ),
                None,
            )
            if matched is None:
                return False
            used_actors.add(matched.actor_id)

        return True


__all__ = [
    "ApprovalWorkflow",
    "CANON_GOVERNANCE_APPROVAL_WORKFLOW",
]

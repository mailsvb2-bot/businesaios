from __future__ import annotations

from typing import Mapping

from governance.approval_contract import ApprovalDecision, ApprovalRecord


CANON_GOVERNANCE_APPROVAL_AUDIT = True


def build_approval_requested_audit(record: ApprovalRecord) -> dict[str, object]:
    request = record.request
    return {
        "event_type": "approval_requested",
        "tenant_id": request.tenant_id,
        "approval_id": request.approval_id,
        "subject_type": request.subject_type,
        "subject_id": request.subject_id,
        "requested_by": request.requested_by,
        "status": record.status.value,
        "required_role_groups": [[role.value for role in group] for group in request.required_role_groups],
        "min_distinct_approvers": request.min_distinct_approvers,
        "prohibit_self_approval": request.prohibit_self_approval,
        "reason": request.reason,
        "metadata": dict(request.metadata),
    }


def build_approval_decision_audit(
    *,
    record: ApprovalRecord,
    decision: ApprovalDecision,
) -> dict[str, object]:
    request = record.request
    return {
        "event_type": "approval_decision_recorded",
        "tenant_id": request.tenant_id,
        "approval_id": request.approval_id,
        "subject_type": request.subject_type,
        "subject_id": request.subject_id,
        "actor_id": decision.actor_id,
        "role_id": decision.role_id.value,
        "outcome": decision.outcome.value,
        "rationale": decision.rationale,
        "status_after": record.status.value,
        "metadata": dict(decision.metadata),
    }


def build_guard_audit(
    *,
    tenant_id: str,
    action_name: str,
    verdict: str,
    reason: str,
    fields: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "event_type": "governance_guard_verdict",
        "tenant_id": str(tenant_id),
        "action_name": str(action_name),
        "verdict": str(verdict),
        "reason": str(reason),
        "fields": dict(fields or {}),
    }


__all__ = [
    "CANON_GOVERNANCE_APPROVAL_AUDIT",
    "build_approval_decision_audit",
    "build_approval_requested_audit",
    "build_guard_audit",
]

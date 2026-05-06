from __future__ import annotations

from datetime import timedelta

import pytest

from governance.approval_contract import (
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalStatus,
    utc_now,
)
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.rbac_contract import RoleId


def build_workflow() -> ApprovalWorkflow:
    return ApprovalWorkflow(store=InMemoryApprovalStore())


def test_approval_workflow_rejects_self_approval_by_default() -> None:
    workflow = build_workflow()
    workflow.submit(
        ApprovalRequest(
            approval_id="ap-1",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="exec-1",
            requested_by="alice",
            reason="need approval",
            required_role_groups=((RoleId.OWNER,),),
        )
    )

    with pytest.raises(RuntimeError, match="self_approval_is_forbidden"):
        workflow.decide(
            ApprovalDecision(
                approval_id="ap-1",
                tenant_id="tenant-a",
                actor_id="alice",
                role_id=RoleId.OWNER,
                outcome=ApprovalOutcome.APPROVE,
                rationale="approve myself",
            )
        )


def test_approval_workflow_requires_distinct_actors_for_dual_control() -> None:
    workflow = build_workflow()
    workflow.submit(
        ApprovalRequest(
            approval_id="ap-2",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="exec-2",
            requested_by="requester",
            reason="strategic change",
            required_role_groups=((RoleId.OWNER,), (RoleId.SECURITY,)),
            min_distinct_approvers=2,
        )
    )

    workflow.decide(
        ApprovalDecision(
            approval_id="ap-2",
            tenant_id="tenant-a",
            actor_id="owner-1",
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale="owner approves",
        )
    )

    record = workflow.get("ap-2")
    assert record is not None
    assert record.status == ApprovalStatus.REQUESTED

    workflow.decide(
        ApprovalDecision(
            approval_id="ap-2",
            tenant_id="tenant-a",
            actor_id="sec-1",
            role_id=RoleId.SECURITY,
            outcome=ApprovalOutcome.APPROVE,
            rationale="security approves",
        )
    )

    record = workflow.get("ap-2")
    assert record is not None
    assert record.status == ApprovalStatus.APPROVED


def test_approval_workflow_rejects_role_outside_required_groups() -> None:
    workflow = build_workflow()
    workflow.submit(
        ApprovalRequest(
            approval_id="ap-3",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="exec-3",
            requested_by="requester",
            reason="budget change",
            required_role_groups=((RoleId.OWNER,), (RoleId.FINANCE,)),
            min_distinct_approvers=2,
        )
    )

    with pytest.raises(RuntimeError, match="decision_role_not_authorized_for_request"):
        workflow.decide(
            ApprovalDecision(
                approval_id="ap-3",
                tenant_id="tenant-a",
                actor_id="ops-1",
                role_id=RoleId.OPERATOR,
                outcome=ApprovalOutcome.APPROVE,
                rationale="operator tries to approve",
            )
        )


def test_approval_workflow_expires_cleanly() -> None:
    workflow = build_workflow()
    workflow.submit(
        ApprovalRequest(
            approval_id="ap-4",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="exec-4",
            requested_by="requester",
            reason="late approval",
            required_role_groups=((RoleId.OWNER,),),
            expires_at=utc_now() + timedelta(milliseconds=1),
        )
    )

    import time
    time.sleep(0.01)

    record = workflow.decide(
        ApprovalDecision(
            approval_id="ap-4",
            tenant_id="tenant-a",
            actor_id="owner-1",
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale="too late",
        )
    )
    assert record.status == ApprovalStatus.EXPIRED

from __future__ import annotations

from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest, ApprovalStatus
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.rbac_contract import RoleId
from runtime.execution import governance_audit_support, governance_runtime, governance_runtime_support


def test_governance_support_is_identity_facade_not_second_runtime() -> None:
    assert governance_runtime_support.review_governance_execution is governance_runtime.review_governance_execution
    assert governance_runtime_support._approval_gate_enabled is governance_runtime._approval_gate_enabled
    assert (
        governance_runtime_support._apply_approval_workflow_resolution
        is governance_runtime._apply_approval_workflow_resolution
    )
    assert (
        governance_runtime_support._append_governance_audit
        is governance_audit_support._append_governance_audit
    )


def test_approval_workflow_resolves_human_approval_without_decisioncore_alias() -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    workflow.submit(
        ApprovalRequest(
            approval_id="approval-wave14",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="execution-1",
            requested_by="requester",
            reason="human approval",
            required_role_groups=((RoleId.OWNER,),),
        )
    )

    record = workflow.resolve(
        ApprovalDecision(
            approval_id="approval-wave14",
            tenant_id="tenant-a",
            actor_id="owner-1",
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale="approved",
        )
    )

    assert record.status is ApprovalStatus.APPROVED
    assert not hasattr(workflow, "decide")

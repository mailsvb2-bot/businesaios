from __future__ import annotations

import pytest

from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.rbac_contract import RoleId


def test_cross_tenant_approval_decision_is_forbidden() -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    workflow.submit(
        ApprovalRequest(
            approval_id='ap-1',
            tenant_id='tenant-a',
            subject_type='action_execution',
            subject_id='exec-1',
            requested_by='user-1',
            reason='need approval',
        )
    )
    with pytest.raises(RuntimeError, match='cross-tenant approval decision is forbidden'):
        workflow.decide(
            ApprovalDecision(
                approval_id='ap-1',
                tenant_id='tenant-b',
                actor_id='user-2',
                role_id=RoleId.OWNER,
                outcome=ApprovalOutcome.APPROVE,
                rationale='approve',
            )
        )

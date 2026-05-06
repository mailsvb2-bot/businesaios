from __future__ import annotations

import json

from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest
from governance.approval_store import PersistentApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.control_plane_audit_log import PersistentGovernanceAuditLog
from governance.rbac_contract import RoleId


def test_approval_workflow_emits_persistent_audit_events(tmp_path) -> None:
    store = PersistentApprovalStore(tmp_path / "approvals.json")
    audit_log = PersistentGovernanceAuditLog(tmp_path / "audit.jsonl")
    workflow = ApprovalWorkflow(store=store, audit_log=audit_log)

    workflow.submit(
        ApprovalRequest(
            approval_id="ap-1",
            tenant_id="tenant-a",
            subject_type="action_execution",
            subject_id="exec-1",
            requested_by="requester",
            reason="budget change",
            required_role_groups=((RoleId.OWNER,),),
        )
    )
    workflow.decide(
        ApprovalDecision(
            approval_id="ap-1",
            tenant_id="tenant-a",
            actor_id="owner-1",
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale="ok",
        )
    )

    rows = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [row["event_type"] for row in rows] == ["approval_requested", "approval_decision_recorded"]
    assert rows[-1]["payload"]["status_after"] == "approved"

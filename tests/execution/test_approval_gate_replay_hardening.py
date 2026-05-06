from __future__ import annotations

from types import SimpleNamespace

from execution.approval_execution_gate import ApprovalExecutionGate
from execution.approval_policy_engine import ApprovalPolicyEngine
from governance.approval_contract import ApprovalDecision, ApprovalOutcome
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.rbac_contract import RoleId
from governance.tenant_policy_overrides import TenantPolicyOverrideRegistry
from runtime.execution.governance_runtime import _build_impact
from runtime.execution.operational_budget_runtime import build_action_execution_context


def _env() -> object:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='exec-approval-hard-1',
            correlation_id='corr-approval-hard-1',
            action='send_email',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'outbound',
                'outbound_count': 1,
                'approval_policy': {'force_human_approval': True, 'auto_submit_approval': True},
                'external_confirmation_mode': 'required',
            },
        )
    )


def test_existing_approval_replay_fails_when_policy_fingerprint_changes() -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    gate = ApprovalExecutionGate(
        approval_policy_engine=ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(tenant_overrides=TenantPolicyOverrideRegistry()),
        ),
        approval_workflow=workflow,
    )
    env = _env()
    ctx = build_action_execution_context(env=env)
    impact = _build_impact(ctx=ctx, payload=env.decision.payload, meta={})

    first = gate.evaluate(
        ctx=ctx,
        impact=impact,
        autonomy_tier='supervised',
        external_confirmation_mode='required',
        approval_policy=env.decision.payload['approval_policy'],
        metadata={'decision_id': 'exec-approval-hard-1'},
        requested_by='owner-1',
    )
    approval_id = first.approval_id
    assert approval_id
    workflow.decide(
        ApprovalDecision(
            approval_id=approval_id,
            tenant_id='tenant-a',
            actor_id='owner-2',
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale='approved',
        )
    )

    replay = gate.evaluate(
        ctx=ctx,
        impact=impact,
        autonomy_tier='supervised',
        external_confirmation_mode='required',
        approval_policy={'force_human_approval': True, 'auto_submit_approval': True, 'required_roles': ['security']},
        metadata={'decision_id': 'exec-approval-hard-1'},
        requested_by='owner-1',
        approval_id=approval_id,
    )
    assert replay.allowed is False
    assert replay.reason == 'approval_request_fingerprint_mismatch'

from __future__ import annotations

from contracts.action_impact_contract import ActionCategory, ActionExecutionContext, ActionImpact
from execution.approval_execution_gate import ApprovalExecutionGate, build_execution_subject_fingerprint
from execution.approval_policy_engine import ApprovalPolicyEngine
from execution.operator_override_contract import (
    OperatorOverrideDecision,
    OperatorOverrideRecord,
    OperatorOverrideRequest,
    OperatorOverrideResolution,
    OperatorOverrideStatus,
)
from governance.approval_contract import ApprovalDecision, ApprovalOutcome
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.rbac_contract import RoleId


def _ctx(*, execution_id: str = 'exec-1', decision_id: str = 'dec-1') -> ActionExecutionContext:
    return ActionExecutionContext(
        tenant_id='tenant-a',
        user_id='user-1',
        action_name='send_email',
        payload={'email': 'x@example.com'},
        metadata={'decision_id': decision_id, 'tags': ['ops']},
        execution_id=execution_id,
    )


def _impact(*, confidence: float = 0.9, category: ActionCategory = ActionCategory.OUTBOUND) -> ActionImpact:
    return ActionImpact(
        action_name='send_email',
        category=category,
        outbound_count=1,
        confidence=confidence,
    )


def _gate() -> tuple[ApprovalExecutionGate, ApprovalWorkflow, InMemoryApprovalStore]:
    store = InMemoryApprovalStore()
    workflow = ApprovalWorkflow(store=store)
    engine = ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy())
    gate = ApprovalExecutionGate(approval_policy_engine=engine, approval_workflow=workflow)
    return gate, workflow, store


def test_policy_engine_disables_manual_override_for_dual_control_unknown_actions() -> None:
    engine = ApprovalPolicyEngine(change_control_policy=ChangeControlPolicy())
    decision = engine.evaluate(
        policy_input=__import__('execution.approval_policy_engine', fromlist=['ApprovalPolicyInput']).ApprovalPolicyInput(
            ctx=_ctx(),
            impact=_impact(category=ActionCategory.UNKNOWN),
            autonomy_tier='full_autonomy',
            external_confirmation_mode='required',
            approval_policy={'allow_operator_override': True},
        )
    )
    assert decision.approval_required is True
    assert decision.manual_override_allowed is False
    assert decision.min_distinct_approvers >= 2


def test_gate_auto_submits_and_then_allows_with_matching_approval() -> None:
    gate, workflow, store = _gate()
    ctx = _ctx()
    impact = _impact()
    verdict = gate.evaluate(ctx=ctx, impact=impact, metadata={'decision_id': 'dec-1'})
    assert verdict.allowed is False
    assert verdict.approval_id is not None
    record = store.get(verdict.approval_id)
    assert record is not None
    approved = workflow.decide(
        ApprovalDecision(
            approval_id=verdict.approval_id,
            tenant_id='tenant-a',
            actor_id='owner-1',
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale='ok',
        )
    )
    assert approved.status.value in {'requested', 'approved'}
    if approved.status.value == 'requested':
        approved = workflow.decide(
            ApprovalDecision(
                approval_id=verdict.approval_id,
                tenant_id='tenant-a',
                actor_id='operator-1',
                role_id=RoleId.OPERATOR,
                outcome=ApprovalOutcome.APPROVE,
                rationale='ok-2',
            )
        )
    assert approved.status.value == 'approved'
    allowed = gate.evaluate(ctx=ctx, impact=impact, metadata={'decision_id': 'dec-1'}, approval_id=verdict.approval_id)
    assert allowed.allowed is True
    assert allowed.reason == 'approval_satisfied'


def test_gate_rejects_mismatched_fingerprint() -> None:
    gate, workflow, _store = _gate()
    ctx = _ctx()
    impact = _impact()
    first = gate.evaluate(ctx=ctx, impact=impact, metadata={'decision_id': 'dec-1'})
    assert first.approval_id
    approved = workflow.decide(
        ApprovalDecision(
            approval_id=first.approval_id,
            tenant_id='tenant-a',
            actor_id='owner-1',
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale='ok',
        )
    )
    if approved.status.value == 'requested':
        workflow.decide(
            ApprovalDecision(
                approval_id=first.approval_id,
                tenant_id='tenant-a',
                actor_id='operator-1',
                role_id=RoleId.OPERATOR,
                outcome=ApprovalOutcome.APPROVE,
                rationale='ok-2',
            )
        )
    mismatched = gate.evaluate(
        ctx=_ctx(decision_id='dec-2'),
        impact=impact,
        metadata={'decision_id': 'dec-2'},
        approval_id=first.approval_id,
    )
    assert mismatched.allowed is False
    assert mismatched.reason == 'approval_subject_mismatch'


def test_operator_override_is_one_shot_and_replay_safe() -> None:
    gate, _workflow, _store = _gate()
    ctx = _ctx()
    impact = _impact(confidence=0.95, category=ActionCategory.INTERNAL_WRITE)
    subject_fingerprint = build_execution_subject_fingerprint(
        ctx=ctx,
        decision_id='dec-1',
        impact=impact,
        external_confirmation_mode='required',
    )
    request = OperatorOverrideRequest(
        override_id='ovr-1',
        tenant_id='tenant-a',
        execution_id='exec-1',
        decision_id='dec-1',
        action_name='send_email',
        requested_by='user-1',
        reason='urgent',
        subject_fingerprint=subject_fingerprint,
    )
    decision = OperatorOverrideDecision(
        override_id='ovr-1',
        tenant_id='tenant-a',
        actor_id='owner-1',
        role_id=RoleId.OWNER,
        resolution=OperatorOverrideResolution.APPROVE_ONCE,
        note='allow once',
    )
    record = OperatorOverrideRecord(request=request, status=OperatorOverrideStatus.APPROVED, decision=decision)
    verdict = gate.evaluate(ctx=ctx, impact=impact, metadata={'decision_id': 'dec-1'}, operator_override=record)
    assert verdict.allowed is True
    consumed = record.consume_once(execution_id='exec-1')
    replay = gate.evaluate(ctx=ctx, impact=impact, metadata={'decision_id': 'dec-1'}, operator_override=consumed)
    assert replay.allowed is False
    assert replay.reason.startswith('operator_override_')


def test_subject_fingerprint_changes_when_payload_values_change() -> None:
    impact = _impact(confidence=0.95, category=ActionCategory.INTERNAL_WRITE)
    fp1 = build_execution_subject_fingerprint(
        ctx=ActionExecutionContext(tenant_id='tenant-a', user_id='user-1', action_name='send_email', payload={'channel': 'email', 'body': 'hello'}, metadata={'decision_id': 'dec-1', 'tags': ['ops']}, execution_id='exec-1'),
        decision_id='dec-1',
        impact=impact,
        external_confirmation_mode='required',
    )
    fp2 = build_execution_subject_fingerprint(
        ctx=ActionExecutionContext(tenant_id='tenant-a', user_id='user-1', action_name='send_email', payload={'channel': 'email', 'body': 'different'}, metadata={'decision_id': 'dec-1', 'tags': ['ops']}, execution_id='exec-1'),
        decision_id='dec-1',
        impact=impact,
        external_confirmation_mode='required',
    )
    assert fp1 != fp2


def test_gate_returns_request_fingerprint_and_expiry_on_auto_submit() -> None:
    gate, _workflow, _store = _gate()
    verdict = gate.evaluate(ctx=_ctx(), impact=_impact(), metadata={'decision_id': 'dec-1'})
    assert verdict.allowed is False
    assert verdict.metadata['approval_request_fingerprint']
    assert verdict.metadata['expires_at']

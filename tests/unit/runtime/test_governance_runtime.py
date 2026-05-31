from __future__ import annotations

from types import SimpleNamespace

from contracts.action_impact_contract import ActionCategory
from execution.approval_execution_gate import build_execution_subject_fingerprint
from execution.operator_override_contract import (
    OperatorOverrideDecision,
    OperatorOverrideRecord,
    OperatorOverrideRequest,
    OperatorOverrideResolution,
    OperatorOverrideStatus,
)
from execution.operator_override_store import InMemoryOperatorOverrideStore
from governance.approval_contract import ApprovalDecision, ApprovalOutcome, ApprovalRequest
from governance.approval_store import InMemoryApprovalStore
from governance.approval_workflow import ApprovalWorkflow
from governance.change_control_policy import ChangeControlPolicy
from governance.control_plane_audit_log import PersistentGovernanceAuditLog
from governance.emergency_stop_guard import EmergencyStopGuard
from governance.kill_switch_registry import KillSwitchRegistry
from governance.permission_matrix import PermissionMatrix
from governance.rbac_contract import RoleId
from governance.rbac_policy import RbacPolicy
from governance.role_catalog import RoleCatalog
from governance.sox_like_action_guard import SoxLikeActionGuard
from governance.tenant_policy_overrides import TenantPolicyOverrideRegistry
from runtime.execution.governance_runtime import GovernanceExecutionBlocked, review_governance_execution


class _Events:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    def emit(self, **kwargs) -> None:
        self.items.append(dict(kwargs))


def _build_guard(*, workflow: ApprovalWorkflow | None = None) -> SoxLikeActionGuard:
    tenant_overrides = TenantPolicyOverrideRegistry()
    return SoxLikeActionGuard(
        rbac_policy=RbacPolicy(
            role_catalog=RoleCatalog(),
            permission_matrix=PermissionMatrix(),
            tenant_overrides=tenant_overrides,
        ),
        emergency_stop_guard=EmergencyStopGuard(registry=KillSwitchRegistry()),
        approval_workflow=workflow or ApprovalWorkflow(store=InMemoryApprovalStore()),
        change_control_policy=ChangeControlPolicy(tenant_overrides=tenant_overrides),
        tenant_overrides=tenant_overrides,
        permission_matrix=PermissionMatrix(),
    )


def test_governance_runtime_is_noop_without_roles_or_enforce_flag() -> None:
    executor = SimpleNamespace(_governance_execution_guard=_build_guard(), _events=_Events())
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d1',
            correlation_id='c1',
            action='change_budget',
            payload={'tenant_id': 'tenant-a', 'user_id': 'u1'},
        )
    )
    review_governance_execution(executor=executor, env=env)
    assert executor._events.items == []


def test_governance_runtime_blocks_when_governance_is_enforced_but_approval_missing() -> None:
    executor = SimpleNamespace(_governance_execution_guard=_build_guard(), _events=_Events())
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d2',
            correlation_id='c2',
            action='change_budget',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'budget_change',
                'cost_minor': 100000,
            },
        )
    )
    try:
        review_governance_execution(executor=executor, env=env)
    except GovernanceExecutionBlocked as exc:
        assert exc.error == 'finance_change_requires_dual_control'
    else:
        raise AssertionError('expected GovernanceExecutionBlocked')
    assert executor._events.items[-1]['event_type'] == 'governance_execution_veto'


def test_governance_runtime_allows_when_matching_approval_is_present() -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    workflow.submit(
        ApprovalRequest(
            approval_id='ap-1',
            tenant_id='tenant-a',
            subject_type='action_execution',
            subject_id='d3',
            requested_by='requester',
            reason='budget change',
            required_role_groups=((RoleId.OWNER,), (RoleId.FINANCE,)),
            min_distinct_approvers=2,
        )
    )
    workflow.decide(
        ApprovalDecision(
            approval_id='ap-1',
            tenant_id='tenant-a',
            actor_id='owner-1',
            role_id=RoleId.OWNER,
            outcome=ApprovalOutcome.APPROVE,
            rationale='owner ok',
        )
    )
    workflow.decide(
        ApprovalDecision(
            approval_id='ap-1',
            tenant_id='tenant-a',
            actor_id='finance-1',
            role_id=RoleId.FINANCE,
            outcome=ApprovalOutcome.APPROVE,
            rationale='finance ok',
        )
    )
    executor = SimpleNamespace(_governance_execution_guard=_build_guard(workflow=workflow), _events=_Events())
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d3',
            correlation_id='c3',
            action='change_budget',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'budget_change',
                'cost_minor': 100000,
                'approval_id': 'ap-1',
            },
        )
    )
    review_governance_execution(executor=executor, env=env)
    assert executor._events.items == []


def test_governance_runtime_auto_submits_execution_approval_for_effectful_autonomy_payload() -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    approval_gate = __import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
        approval_policy_engine=__import__('execution.approval_policy_engine', fromlist=['ApprovalPolicyEngine']).ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(),
        ),
        approval_workflow=workflow,
    )
    executor = SimpleNamespace(
        _governance_execution_guard=_build_guard(workflow=workflow),
        _approval_execution_gate=approval_gate,
        _events=_Events(),
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d4',
            correlation_id='c4',
            action='send_email',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'outbound',
                'outbound_count': 1,
                'approval_policy': {'force_human_approval': True},
                'external_confirmation_mode': 'required',
            },
        )
    )
    try:
        review_governance_execution(executor=executor, env=env)
    except GovernanceExecutionBlocked as exc:
        assert exc.output['approval']['approval_id']
        assert exc.output['approval']['subject_fingerprint']
        assert exc.output['approval_required'] is True
        assert exc.output['operator_required'] is True
    else:
        raise AssertionError('expected GovernanceExecutionBlocked')


def test_governance_runtime_allows_when_execution_approval_is_satisfied() -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    approval_gate = __import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
        approval_policy_engine=__import__('execution.approval_policy_engine', fromlist=['ApprovalPolicyEngine']).ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(),
        ),
        approval_workflow=workflow,
    )
    executor = SimpleNamespace(
        _governance_execution_guard=_build_guard(workflow=workflow),
        _approval_execution_gate=approval_gate,
        _events=_Events(),
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d5',
            correlation_id='c5',
            action='send_email',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'outbound',
                'outbound_count': 1,
                'approval_policy': {'force_human_approval': True},
                'external_confirmation_mode': 'required',
            },
        )
    )
    try:
        review_governance_execution(executor=executor, env=env)
    except GovernanceExecutionBlocked as exc:
        approval_id = exc.output['approval']['approval_id']
    else:
        raise AssertionError('expected first pass to block')
    workflow.decide(ApprovalDecision(approval_id=approval_id, tenant_id='tenant-a', actor_id='owner-1b', role_id=RoleId.OWNER, outcome=ApprovalOutcome.APPROVE, rationale='ok'))
    env.decision.payload['approval_id'] = approval_id
    review_governance_execution(executor=executor, env=env)


def test_governance_runtime_consumes_operator_override_once() -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    approval_gate = __import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
        approval_policy_engine=__import__('execution.approval_policy_engine', fromlist=['ApprovalPolicyEngine']).ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(),
        ),
        approval_workflow=workflow,
    )
    override_store = InMemoryOperatorOverrideStore()
    executor = SimpleNamespace(
        _governance_execution_guard=_build_guard(workflow=workflow),
        _approval_execution_gate=approval_gate,
        _operator_override_store=override_store,
        _events=_Events(),
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d6',
            correlation_id='c6',
            action='send_email',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'outbound',
                'outbound_count': 1,
                'approval_policy': {'force_human_approval': True, 'allow_operator_override': True},
                'external_confirmation_mode': 'required',
            },
        )
    )
    impact = __import__('contracts.action_impact_contract', fromlist=['ActionImpact']).ActionImpact(
        action_name='send_email',
        category=ActionCategory.OUTBOUND,
        outbound_count=1,
    )
    ctx = __import__('runtime.execution.operational_budget_runtime', fromlist=['build_action_execution_context']).build_action_execution_context(env=env)
    fingerprint = build_execution_subject_fingerprint(ctx=ctx, decision_id='d6', impact=impact, external_confirmation_mode='required')
    request = OperatorOverrideRequest(
        override_id='ovr-1',
        tenant_id='tenant-a',
        execution_id='d6',
        decision_id='d6',
        action_name='send_email',
        requested_by='owner-1',
        reason='allow once',
        subject_fingerprint=fingerprint,
        metadata={'impact_category': 'outbound'},
    )
    record = override_store.create(request)
    approved = OperatorOverrideRecord(
        request=record.request,
        status=OperatorOverrideStatus.APPROVED,
        decision=OperatorOverrideDecision(
            override_id='ovr-1',
            tenant_id='tenant-a',
            actor_id='owner-2',
            role_id=RoleId.OWNER,
            resolution=OperatorOverrideResolution.APPROVE_ONCE,
            note='approved once',
        ),
        final_reason='override_approved_once',
    )
    override_store.save(approved)
    env.decision.payload['operator_override_id'] = 'ovr-1'
    review_governance_execution(executor=executor, env=env)
    saved = override_store.get('ovr-1')
    assert saved is not None
    assert saved.status is OperatorOverrideStatus.CONSUMED
    assert saved.consumed_by_execution_id == 'd6'
    assert any(item['event_type'] == 'governance_execution_operator_override_consumed' for item in executor._events.items)
    try:
        review_governance_execution(executor=executor, env=env)
    except GovernanceExecutionBlocked as exc:
        assert exc.error.startswith('operator_override_')
    else:
        raise AssertionError('expected replay with consumed override to block')




def test_governance_runtime_blocked_output_contains_resume_hint() -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    approval_gate = __import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
        approval_policy_engine=__import__('execution.approval_policy_engine', fromlist=['ApprovalPolicyEngine']).ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(),
        ),
        approval_workflow=workflow,
    )
    executor = SimpleNamespace(
        _governance_execution_guard=_build_guard(workflow=workflow),
        _approval_execution_gate=approval_gate,
        _events=_Events(),
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d-resume',
            correlation_id='c-resume',
            action='send_email',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'outbound',
                'outbound_count': 1,
                'approval_policy': {'force_human_approval': True},
                'external_confirmation_mode': 'required',
            },
        )
    )
    try:
        review_governance_execution(executor=executor, env=env)
    except GovernanceExecutionBlocked as exc:
        resume = exc.output['governance']['resume']
        assert resume['resume_stage'] == 'governance_approval'
        assert resume['execution_id'] == 'd-resume'
        assert resume['approval_id'] == exc.output['approval']['approval_id']
        assert resume['subject_fingerprint'] == exc.output['approval']['subject_fingerprint']
    else:
        raise AssertionError('expected GovernanceExecutionBlocked')


def test_governance_runtime_emits_resume_hint_and_resume_ready_events() -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    approval_gate = __import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
        approval_policy_engine=__import__('execution.approval_policy_engine', fromlist=['ApprovalPolicyEngine']).ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(),
        ),
        approval_workflow=workflow,
    )
    executor = SimpleNamespace(
        _governance_execution_guard=_build_guard(workflow=workflow),
        _approval_execution_gate=approval_gate,
        _events=_Events(),
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d7',
            correlation_id='c7',
            action='send_email',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'outbound',
                'outbound_count': 1,
                'approval_policy': {'force_human_approval': True},
                'external_confirmation_mode': 'required',
            },
        )
    )
    try:
        review_governance_execution(executor=executor, env=env)
    except GovernanceExecutionBlocked as exc:
        approval_id = exc.output['approval']['approval_id']
    else:
        raise AssertionError('expected first pass to block')
    assert any(item['event_type'] == 'governance_execution_resume_hint_emitted' for item in executor._events.items)

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
    env.decision.payload['approval_id'] = approval_id
    review_governance_execution(executor=executor, env=env)
    resume_ready = [item for item in executor._events.items if item['event_type'] == 'governance_execution_resume_ready']
    assert resume_ready
    assert resume_ready[-1]['payload']['resume']['approval_id'] == approval_id




def test_governance_runtime_persists_resume_audit_events(tmp_path) -> None:
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore())
    audit_log = PersistentGovernanceAuditLog(tmp_path / 'governance_audit.jsonl')
    approval_gate = __import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
        approval_policy_engine=__import__('execution.approval_policy_engine', fromlist=['ApprovalPolicyEngine']).ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(),
        ),
        approval_workflow=workflow,
        audit_log=audit_log,
    )
    guard = _build_guard(workflow=workflow)
    setattr(guard, '_audit_log', audit_log)
    executor = SimpleNamespace(
        _governance_execution_guard=guard,
        _approval_execution_gate=approval_gate,
        _events=_Events(),
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d-audit',
            correlation_id='c-audit',
            action='send_email',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'outbound',
                'outbound_count': 1,
                'approval_policy': {'force_human_approval': True},
                'external_confirmation_mode': 'required',
            },
        )
    )
    try:
        review_governance_execution(executor=executor, env=env)
    except GovernanceExecutionBlocked as exc:
        approval_id = exc.output['approval']['approval_id']
    else:
        raise AssertionError('expected GovernanceExecutionBlocked')

    events = audit_log.summarize_tenant_lifecycle('tenant-a')
    assert events['lifecycle_counts']['approval_required'] >= 1
    assert events['lifecycle_counts']['resume_hint_emitted'] >= 1

    workflow.decide(ApprovalDecision(approval_id=approval_id, tenant_id='tenant-a', actor_id='owner-2', role_id=RoleId.OWNER, outcome=ApprovalOutcome.APPROVE, rationale='ok'))
    env.decision.payload['approval_id'] = approval_id
    review_governance_execution(executor=executor, env=env)

    reloaded = PersistentGovernanceAuditLog(tmp_path / 'governance_audit.jsonl')
    summary = reloaded.summarize_tenant_lifecycle('tenant-a')
    assert summary['lifecycle_counts']['resume_ready'] >= 1



def test_governance_runtime_persists_consumed_and_satisfied_events_to_audit(tmp_path) -> None:
    audit_log = PersistentGovernanceAuditLog(tmp_path / 'governance_audit.jsonl')
    workflow = ApprovalWorkflow(store=InMemoryApprovalStore(), audit_log=audit_log)
    approval_gate = __import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
        approval_policy_engine=__import__('execution.approval_policy_engine', fromlist=['ApprovalPolicyEngine']).ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(),
        ),
        approval_workflow=workflow,
        audit_log=audit_log,
    )
    guard = _build_guard(workflow=workflow)
    setattr(guard, '_audit_log', audit_log)
    override_store = InMemoryOperatorOverrideStore()
    executor = SimpleNamespace(
        _governance_execution_guard=guard,
        _approval_execution_gate=approval_gate,
        _operator_override_store=override_store,
        _events=_Events(),
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='d-audit',
            correlation_id='c-audit',
            action='send_email',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'outbound',
                'outbound_count': 1,
                'approval_policy': {'force_human_approval': True, 'allow_operator_override': True},
                'external_confirmation_mode': 'required',
                'operator_override_id': 'ovr-audit',
            },
        )
    )
    impact = __import__('contracts.action_impact_contract', fromlist=['ActionImpact']).ActionImpact(
        action_name='send_email',
        category=ActionCategory.OUTBOUND,
        outbound_count=1,
    )
    ctx = __import__('runtime.execution.operational_budget_runtime', fromlist=['build_action_execution_context']).build_action_execution_context(env=env)
    fingerprint = build_execution_subject_fingerprint(ctx=ctx, decision_id='d-audit', impact=impact, external_confirmation_mode='required')
    record = override_store.create(
        OperatorOverrideRequest(
            override_id='ovr-audit',
            tenant_id='tenant-a',
            execution_id='d-audit',
            decision_id='d-audit',
            action_name='send_email',
            requested_by='owner-1',
            reason='allow once',
            subject_fingerprint=fingerprint,
            metadata={'impact_category': 'outbound'},
        )
    )
    override_store.save(
        OperatorOverrideRecord(
            request=record.request,
            status=OperatorOverrideStatus.APPROVED,
            decision=OperatorOverrideDecision(
                override_id='ovr-audit',
                tenant_id='tenant-a',
                actor_id='owner-2',
                role_id=RoleId.OWNER,
                resolution=OperatorOverrideResolution.APPROVE_ONCE,
                note='approved once',
            ),
            final_reason='override_approved_once',
        )
    )
    review_governance_execution(executor=executor, env=env)
    summary = audit_log.summarize_tenant_lifecycle('tenant-a', limit=200)
    assert summary['lifecycle_counts']['override_consumed'] >= 1
    assert summary['lifecycle_counts']['approval_satisfied'] >= 1

from __future__ import annotations

from types import SimpleNamespace

from contracts.action_impact_contract import ActionCategory
from execution.approval_execution_gate import build_execution_subject_fingerprint
from execution.approval_policy_engine import ApprovalPolicyEngine
from execution.operator_override_contract import (
    OperatorOverrideDecision,
    OperatorOverrideRecord,
    OperatorOverrideRequest,
    OperatorOverrideResolution,
    OperatorOverrideStatus,
)
from execution.operator_override_store import PersistentOperatorOverrideStore
from governance.approval_store import PersistentApprovalStore
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
from interfaces.api.approval_route_handlers import ApprovalRouteHandlers
from runtime.execution.governance_runtime import GovernanceExecutionBlocked, review_governance_execution
from runtime.execution.operational_budget_runtime import build_action_execution_context
from app.web.pages.approvals import ApprovalsPage


class _Events:
    def __init__(self) -> None:
        self.items: list[dict[str, object]] = []

    def emit(self, **kwargs) -> None:
        self.items.append(dict(kwargs))


def _build_guard(*, workflow: ApprovalWorkflow) -> SoxLikeActionGuard:
    tenant_overrides = TenantPolicyOverrideRegistry()
    return SoxLikeActionGuard(
        rbac_policy=RbacPolicy(
            role_catalog=RoleCatalog(),
            permission_matrix=PermissionMatrix(),
            tenant_overrides=tenant_overrides,
        ),
        emergency_stop_guard=EmergencyStopGuard(registry=KillSwitchRegistry()),
        approval_workflow=workflow,
        change_control_policy=ChangeControlPolicy(tenant_overrides=tenant_overrides),
        tenant_overrides=tenant_overrides,
        permission_matrix=PermissionMatrix(),
    )


def test_approval_resume_replay_persistence_flow(tmp_path) -> None:
    approval_store = PersistentApprovalStore(tmp_path / 'approvals.json')
    override_store = PersistentOperatorOverrideStore(tmp_path / 'overrides.json')
    audit_log = PersistentGovernanceAuditLog(tmp_path / 'audit.jsonl')
    workflow = ApprovalWorkflow(store=approval_store, audit_log=audit_log)
    guard = _build_guard(workflow=workflow)
    approval_gate = __import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
        approval_policy_engine=ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(tenant_overrides=TenantPolicyOverrideRegistry()),
        ),
        approval_workflow=workflow,
        audit_log=audit_log,
    )

    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='exec-approval-1',
            correlation_id='corr-approval-1',
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
    executor = SimpleNamespace(
        _governance_execution_guard=guard,
        _approval_execution_gate=approval_gate,
        _events=_Events(),
        _operator_override_store=override_store,
    )

    try:
        review_governance_execution(executor=executor, env=env)
    except GovernanceExecutionBlocked as exc:
        blocked = exc.output
    else:
        raise AssertionError('expected governance block')

    approval_id = blocked['approval']['approval_id']
    assert approval_id
    handlers = ApprovalRouteHandlers(
        approval_store=approval_store,
        operator_override_store=override_store,
        audit_log=audit_log,
    )
    handlers.decide(
        approval_id=approval_id,
        tenant_id='tenant-a',
        actor_id='owner-2',
        role_id=RoleId.OWNER,
        outcome=__import__('governance.approval_contract', fromlist=['ApprovalOutcome']).ApprovalOutcome.APPROVE,
        rationale='approved after halt',
    )

    # Restart and replay the same execution with the persisted approval.
    restarted_executor = SimpleNamespace(
        _governance_execution_guard=_build_guard(workflow=ApprovalWorkflow(store=PersistentApprovalStore(tmp_path / 'approvals.json'), audit_log=PersistentGovernanceAuditLog(tmp_path / 'audit.jsonl'))),
        _approval_execution_gate=__import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
            approval_policy_engine=ApprovalPolicyEngine(
                change_control_policy=ChangeControlPolicy(tenant_overrides=TenantPolicyOverrideRegistry()),
            ),
            approval_workflow=ApprovalWorkflow(store=PersistentApprovalStore(tmp_path / 'approvals.json'), audit_log=PersistentGovernanceAuditLog(tmp_path / 'audit.jsonl')),
            audit_log=PersistentGovernanceAuditLog(tmp_path / 'audit.jsonl'),
        ),
        _events=_Events(),
        _operator_override_store=PersistentOperatorOverrideStore(tmp_path / 'overrides.json'),
    )
    env_replay = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='exec-approval-1',
            correlation_id='corr-approval-1b',
            action='send_email',
            payload={
                **env.decision.payload,
                'approval_id': approval_id,
            },
        )
    )
    review_governance_execution(executor=restarted_executor, env=env_replay)

    listing = handlers.list_open(tenant_id='tenant-a')
    assert listing['audit']['integrity']['valid'] is True
    assert listing['audit']['lifecycle_counts']['approval_requested'] >= 1
    assert listing['audit']['lifecycle_counts']['approval_decided'] >= 1
    assert listing['audit']['lifecycle_counts']['resume_ready'] >= 1

    page = ApprovalsPage().build({'tenant_id': 'tenant-a', 'queue': listing, 'audit': listing['audit']})
    assert page['payload']['summary']['audit_integrity_valid'] is True
    assert page['payload']['operator_console']['resume_ready_event_count'] >= 1


def test_operator_override_replay_is_consumed_and_persists_across_restart(tmp_path) -> None:
    approval_store = PersistentApprovalStore(tmp_path / 'approvals2.json')
    override_store = PersistentOperatorOverrideStore(tmp_path / 'overrides2.json')
    audit_log = PersistentGovernanceAuditLog(tmp_path / 'audit2.jsonl')
    workflow = ApprovalWorkflow(store=approval_store, audit_log=audit_log)
    guard = _build_guard(workflow=workflow)
    approval_gate = __import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
        approval_policy_engine=ApprovalPolicyEngine(
            change_control_policy=ChangeControlPolicy(tenant_overrides=TenantPolicyOverrideRegistry()),
        ),
        approval_workflow=workflow,
        audit_log=audit_log,
    )

    base_env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='exec-override-1',
            correlation_id='corr-override-1',
            action='send_email',
            payload={
                'tenant_id': 'tenant-a',
                'user_id': 'owner-1',
                'role_ids': ['owner'],
                'action_category': 'outbound',
                'outbound_count': 1,
                'approval_policy': {'allow_operator_override': True, 'force_human_approval': True},
                'external_confirmation_mode': 'required',
            },
        )
    )
    ctx = build_action_execution_context(env=base_env)
    impact = __import__('runtime.execution.governance_runtime', fromlist=['_build_impact'])._build_impact(
        ctx=ctx,
        payload=base_env.decision.payload,
        meta={},
    )
    fingerprint = build_execution_subject_fingerprint(
        ctx=ctx,
        decision_id='exec-override-1',
        impact=impact,
        external_confirmation_mode='required',
    )
    created = override_store.create(
        OperatorOverrideRequest(
            override_id='ovr-persist-1',
            tenant_id='tenant-a',
            execution_id='exec-override-1',
            decision_id='exec-override-1',
            action_name='send_email',
            requested_by='owner-1',
            reason='allow exactly once',
            subject_fingerprint=fingerprint,
            metadata={'impact_category': ActionCategory.OUTBOUND.value},
        )
    )
    override_store.save(
        OperatorOverrideRecord(
            request=created.request,
            status=OperatorOverrideStatus.APPROVED,
            decision=OperatorOverrideDecision(
                override_id='ovr-persist-1',
                tenant_id='tenant-a',
                actor_id='owner-2',
                role_id=RoleId.OWNER,
                resolution=OperatorOverrideResolution.APPROVE_ONCE,
                note='approved once',
            ),
            final_reason='override_approved_once',
        )
    )

    executor = SimpleNamespace(
        _governance_execution_guard=guard,
        _approval_execution_gate=approval_gate,
        _events=_Events(),
        _operator_override_store=override_store,
    )
    env = SimpleNamespace(
        decision=SimpleNamespace(
            decision_id='exec-override-1',
            correlation_id='corr-override-1',
            action='send_email',
            payload={
                **base_env.decision.payload,
                'operator_override_id': 'ovr-persist-1',
            },
        )
    )
    review_governance_execution(executor=executor, env=env)

    reloaded_override_store = PersistentOperatorOverrideStore(tmp_path / 'overrides2.json')
    consumed = reloaded_override_store.get('ovr-persist-1')
    assert consumed is not None
    assert consumed.status is OperatorOverrideStatus.CONSUMED

    replay_executor = SimpleNamespace(
        _governance_execution_guard=_build_guard(workflow=ApprovalWorkflow(store=PersistentApprovalStore(tmp_path / 'approvals2.json'), audit_log=PersistentGovernanceAuditLog(tmp_path / 'audit2.jsonl'))),
        _approval_execution_gate=__import__('execution.approval_execution_gate', fromlist=['ApprovalExecutionGate']).ApprovalExecutionGate(
            approval_policy_engine=ApprovalPolicyEngine(
                change_control_policy=ChangeControlPolicy(tenant_overrides=TenantPolicyOverrideRegistry()),
            ),
            approval_workflow=ApprovalWorkflow(store=PersistentApprovalStore(tmp_path / 'approvals2.json'), audit_log=PersistentGovernanceAuditLog(tmp_path / 'audit2.jsonl')),
            audit_log=PersistentGovernanceAuditLog(tmp_path / 'audit2.jsonl'),
        ),
        _events=_Events(),
        _operator_override_store=reloaded_override_store,
    )
    with __import__('pytest').raises(GovernanceExecutionBlocked) as exc:
        review_governance_execution(executor=replay_executor, env=env)
    assert 'operator_override_invalid' in exc.value.error

    handlers = ApprovalRouteHandlers(
        approval_store=PersistentApprovalStore(tmp_path / 'approvals2.json'),
        operator_override_store=reloaded_override_store,
        audit_log=PersistentGovernanceAuditLog(tmp_path / 'audit2.jsonl'),
    )
    override_listing = handlers.list_open_operator_overrides(tenant_id='tenant-a')
    assert override_listing['audit']['integrity']['valid'] is True
    assert override_listing['summary']['lifecycle_counts']['consumed'] == 1
    page = ApprovalsPage().build({'tenant_id': 'tenant-a', 'operator_overrides': override_listing, 'audit': override_listing['audit']})
    assert page['payload']['summary']['audit_integrity_valid'] is True
    assert page['payload']['summary']['override_fingerprint_bound_count'] == 0

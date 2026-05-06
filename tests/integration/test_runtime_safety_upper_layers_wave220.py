from __future__ import annotations

from pathlib import Path

from bootstrap.safety_control_boot import build_safety_control_runtime
from config.tenant_config_store import TenantConfigSnapshot
from core.safety.controls.action_identity import canonical_action_id
from core.safety.controls.multi_step_approval.models import ApprovalTicket, ApprovalWorkflowState
from core.safety.controls.rollback_engine.models import RollbackAction, RollbackExecutionState, RollbackPlan
from runtime.safety_controls import evaluate_runtime_action_controls, record_action_success


def _seed_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv('BUSINESAIOS_SAFETY_DATA_DIR', str(tmp_path / 'safety'))
    monkeypatch.setenv('BUSINESAIOS_TENANT_CONFIG_STORE_PATH', str(tmp_path / 'tenant_config.json'))
    monkeypatch.setenv('BUSINESAIOS_TENANT_CONFIG_AUDIT_LOG_PATH', str(tmp_path / 'tenant_config_audit.jsonl'))
    build_safety_control_runtime.cache_clear()
    return build_safety_control_runtime(persistent=True)


def test_policy_trust_chain_persists_lineage(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    store = runtime.profile.tenant_policy_resolver.tenant_config_store
    store.save(TenantConfigSnapshot(tenant_id='t-chain', policy_overrides={'safety_profile': {'action_budget_max_actions': 7}}), actor='test', reason='v1')
    runtime.profile.tenant_policy_resolver.manifest_for('t-chain', 'safety_profile')
    store.save(TenantConfigSnapshot(tenant_id='t-chain', policy_overrides={'safety_profile': {'action_budget_max_actions': 8}}), actor='test', reason='v2')
    runtime.profile.tenant_policy_resolver.manifest_for('t-chain', 'safety_profile')
    lineage = runtime.profile.policy_trust_chain.lineage(tenant_id='t-chain', policy_scope='safety_profile')
    assert len(lineage) >= 2
    assert runtime.profile.policy_trust_chain.verify_lineage(tenant_id='t-chain', policy_scope='safety_profile') is True


def test_approval_guard_escalates_near_expiry(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    action_id = 'ap-escalate'
    runtime.profile.approval_repository.put(ApprovalTicket(action_id=action_id, approvals=('a',), state=ApprovalWorkflowState.PENDING, expires_at='2099-01-01T00:10:00+00:00'))
    payload = {'tenant_id': 't1', 'approval_id': action_id, 'approval_required': True}
    decisions = evaluate_runtime_action_controls(action='deploy_policy@v1', payload=payload)
    approval = next(item for item in decisions if item.control == 'multi_step_approval')
    assert approval.status.value == 'block'
    ticket = runtime.profile.approval_repository.get(action_id)
    assert int(ticket.required_approvals) >= 2


def test_rollback_verification_emits_success_event(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    runtime.profile.rollback_planner._registry.register(
        'rollback_policy@v1',
        lambda ctx: RollbackPlan(source_action=ctx.action, steps=(RollbackAction(action='restore_policy@v1', payload={'tenant_id': ctx.tenant_id}),)),
    )
    payload = {
        'tenant_id': 't1',
        'idempotency_key': 'rb-verify',
        'rollback_verification_required': True,
        'rollback_expected_state': {'policy_version': 'v1'},
        'rollback_observed_state': {'policy_version': 'v1'},
    }
    record_action_success(action='rollback_policy@v1', payload=payload)
    text = Path(runtime.profile.event_store.path).read_text(encoding='utf-8')
    assert 'rollback_verified' in text


def test_safety_supervisor_exports_anomaly_metrics(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    runtime.profile.approval_repository.tickets['ap-metrics-2'] = ApprovalTicket(action_id='ap-metrics-2', approvals=('a', 'b'), state=ApprovalWorkflowState.APPROVED)
    payload = {
        'tenant_id': 't1',
        'approval_id': 'ap-metrics-2',
        'expected_reward': 1.0,
        'expected_margin': 0.3,
        'simulation_required': True,
        'simulation_score': 0.95,
        'simulation_provenance': 'sim',
        'simulation_verified': True,
    }
    for _ in range(6):
        evaluate_runtime_action_controls(action='deploy_policy@v1', payload=payload)
    snap = runtime.profile.tenant_metrics_registry.metric_snapshot(tenant_id='t1', metric_name='safety.anomaly.active')
    assert snap is not None

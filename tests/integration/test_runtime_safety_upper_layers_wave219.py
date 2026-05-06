from __future__ import annotations

import sqlite3
from pathlib import Path

from bootstrap.safety_control_boot import build_safety_control_runtime
from config.tenant_config_store import TenantConfigSnapshot
from core.safety.controls.action_identity import canonical_action_id
from core.safety.controls.multi_step_approval.models import ApprovalTicket, ApprovalWorkflowState
from core.safety.controls.rollback_engine.models import RollbackAction, RollbackExecutionState, RollbackPlan
from runtime.safety_controls import evaluate_runtime_action_controls, record_action_failure, record_action_success


def _seed_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv('BUSINESAIOS_SAFETY_DATA_DIR', str(tmp_path / 'safety'))
    monkeypatch.setenv('BUSINESAIOS_TENANT_CONFIG_STORE_PATH', str(tmp_path / 'tenant_config.json'))
    monkeypatch.setenv('BUSINESAIOS_TENANT_CONFIG_AUDIT_LOG_PATH', str(tmp_path / 'tenant_config_audit.jsonl'))
    build_safety_control_runtime.cache_clear()
    return build_safety_control_runtime(persistent=True)


def test_policy_manifest_is_signed_and_versioned(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    store = runtime.profile.tenant_policy_resolver.tenant_config_store
    store.save(TenantConfigSnapshot(tenant_id='t-manifest', policy_overrides={'safety_profile': {'action_budget_max_actions': 7}}), actor='test', reason='manifest')
    manifest = runtime.profile.tenant_policy_resolver.manifest_for('t-manifest', 'safety_profile')
    assert manifest.version_id
    assert runtime.profile.policy_manifest_signer.verify(manifest) is True


def test_approval_repository_supports_rejections_and_state(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    repo = runtime.profile.approval_repository
    action_id = 'ap-reject'
    repo.record_rejection(action_id=action_id, approver='risk_officer')
    ticket = repo.get(action_id)
    assert ticket.state is ApprovalWorkflowState.REJECTED


def test_rollback_confirmation_loop_persists_execution_state(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    runtime.profile.rollback_planner._registry.register(
        'deploy_policy@v1',
        lambda ctx: RollbackPlan(source_action=ctx.action, steps=(RollbackAction(action='rollback_policy@v1', payload={'tenant_id': ctx.tenant_id}),)),
    )
    payload = {'tenant_id': 't1', 'idempotency_key': 'idem-2'}
    record_action_failure(action='deploy_policy@v1', payload=payload)
    action_id = canonical_action_id(action='deploy_policy@v1', tenant_id='t1', payload=payload)
    plan = runtime.profile.rollback_planner.get_persisted(tenant_id='t1', action_id=action_id)
    assert plan is not None
    assert plan.execution_state is RollbackExecutionState.CONFIRMED
    record_action_success(action='deploy_policy@v1', payload=payload)
    plan2 = runtime.profile.rollback_planner.get_persisted(tenant_id='t1', action_id=action_id)
    assert plan2 is not None
    assert plan2.execution_state is RollbackExecutionState.EXECUTED


def test_safety_event_store_exports_metrics(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    runtime.profile.approval_repository.tickets['ap-metrics'] = ApprovalTicket(action_id='ap-metrics', approvals=('a', 'b'), state=ApprovalWorkflowState.APPROVED)
    payload = {
        'tenant_id': 't1',
        'approval_id': 'ap-metrics',
        'expected_reward': 1.0,
        'expected_margin': 0.3,
        'simulation_required': True,
        'simulation_score': 0.92,
        'simulation_provenance': 'sim',
        'simulation_verified': True,
    }
    evaluate_runtime_action_controls(action='deploy_policy@v1', payload=payload)
    snap = runtime.profile.tenant_metrics_registry.metric_snapshot(tenant_id='t1', metric_name='safety.events.total')
    assert snap is not None
    assert float(snap['value']) >= 1.0


def test_safety_sqlite_schema_migrations_apply(monkeypatch, tmp_path: Path) -> None:
    _seed_runtime(monkeypatch, tmp_path)
    db = Path(tmp_path / 'safety' / 'approval.sqlite3')
    conn = sqlite3.connect(db)
    try:
        row = conn.execute("SELECT version FROM safety_schema_version WHERE component = 'approval_tickets'").fetchone()
    finally:
        conn.close()
    assert row is not None
    assert int(row[0]) >= 2

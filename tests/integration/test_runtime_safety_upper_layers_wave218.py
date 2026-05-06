from __future__ import annotations

from pathlib import Path

from bootstrap.safety_control_boot import build_safety_control_runtime
from config.tenant_config_store import PersistentTenantConfigStore, TenantConfigSnapshot
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.action_identity import canonical_action_id
from core.safety.controls.multi_step_approval.models import ApprovalTicket
from core.safety.controls.rollback_engine.models import RollbackAction, RollbackPlan
from runtime.safety_controls import evaluate_runtime_action_controls, record_action_failure


def _seed_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv('BUSINESAIOS_SAFETY_DATA_DIR', str(tmp_path / 'safety'))
    monkeypatch.setenv('BUSINESAIOS_TENANT_CONFIG_STORE_PATH', str(tmp_path / 'tenant_config.json'))
    monkeypatch.setenv('BUSINESAIOS_TENANT_CONFIG_AUDIT_LOG_PATH', str(tmp_path / 'tenant_config_audit.jsonl'))
    build_safety_control_runtime.cache_clear()
    return build_safety_control_runtime(persistent=True)


def test_persistent_approval_repository_roundtrip(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    runtime.profile.approval_repository.tickets['ap-1'] = ApprovalTicket(action_id='ap-1', approvals=('alice', 'bob'))
    build_safety_control_runtime.cache_clear()
    runtime2 = build_safety_control_runtime(persistent=True)
    ticket = runtime2.profile.approval_repository.get('ap-1')
    assert ticket.approvals == ('alice', 'bob')


def test_tenant_policy_override_applies_to_runtime_controls(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    store = runtime.profile.tenant_policy_resolver.tenant_config_store
    assert isinstance(store, PersistentTenantConfigStore)
    store.save(
        TenantConfigSnapshot(
            tenant_id='t-tight',
            policy_overrides={'safety_profile': {'action_budget_max_actions': 1}},
        ),
        actor='test',
        reason='tight budget',
    )
    payload = {'tenant_id': 't-tight', 'estimated_cost': 1.0}
    decisions_first = evaluate_runtime_action_controls(action='send_marketing_offer@v1', payload=payload)
    assert all(item.reason != 'action_budget_exceeded' for item in decisions_first)
    from runtime.safety_controls import record_allowed_action
    record_allowed_action(action='send_marketing_offer@v1', payload=payload)
    decisions_second = evaluate_runtime_action_controls(action='send_marketing_offer@v1', payload=payload)
    assert any(item.reason == 'action_budget_exceeded' for item in decisions_second)


def test_simulation_signature_verification(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    base_payload = {'tenant_id': 't1', 'simulation_required': True}
    ctx = SafetyActionContext(action='deploy_policy@v1', tenant_id='t1', user_id=None, payload=base_payload, metadata={})
    signature = runtime.profile.simulation_evidence_verifier.sign(ctx=ctx, score=0.91, provenance='signed_sim')
    decisions = evaluate_runtime_action_controls(
        action='deploy_policy@v1',
        payload={
            **base_payload,
            'simulation_score': 0.91,
            'simulation_provenance': 'signed_sim',
            'simulation_verified': True,
            'simulation_signature': signature,
            'approval_id': 'ap-signed',
        },
    )
    runtime.profile.approval_repository.tickets['ap-signed'] = ApprovalTicket(action_id='ap-signed', approvals=('a', 'b'))
    decisions = evaluate_runtime_action_controls(
        action='deploy_policy@v1',
        payload={
            **base_payload,
            'simulation_score': 0.91,
            'simulation_provenance': 'signed_sim',
            'simulation_verified': True,
            'simulation_signature': signature,
            'approval_id': 'ap-signed',
            'expected_reward': 1.0,
            'expected_margin': 0.4,
        },
    )
    assert not any(item.control == 'simulation_gate' and item.reason == 'simulation_gate_blocked' for item in decisions)


def test_rollback_plan_persists_on_failure(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    runtime.profile.rollback_planner._registry.register(
        'deploy_policy@v1',
        lambda ctx: RollbackPlan(source_action=ctx.action, steps=(RollbackAction(action='rollback_policy@v1', payload={'tenant_id': ctx.tenant_id}),)),
    )
    payload = {'tenant_id': 't1', 'idempotency_key': 'idem-1'}
    record_action_failure(action='deploy_policy@v1', payload=payload)
    action_id = canonical_action_id(action='deploy_policy@v1', tenant_id='t1', payload=payload)
    plan = runtime.profile.rollback_planner.get_persisted(tenant_id='t1', action_id=action_id)
    assert plan is not None
    assert plan.steps and plan.steps[0].action == 'rollback_policy@v1'


def test_safety_event_store_records_decisions_and_outcomes(monkeypatch, tmp_path: Path) -> None:
    runtime = _seed_runtime(monkeypatch, tmp_path)
    runtime.profile.approval_repository.tickets['ap-evt'] = ApprovalTicket(action_id='ap-evt', approvals=('a', 'b'))
    payload = {
        'tenant_id': 't1',
        'approval_id': 'ap-evt',
        'expected_reward': 1.0,
        'expected_margin': 0.3,
        'simulation_required': True,
        'simulation_score': 0.92,
        'simulation_provenance': 'sim',
        'simulation_verified': True,
    }
    evaluate_runtime_action_controls(action='deploy_policy@v1', payload=payload)
    record_action_failure(action='deploy_policy@v1', payload=payload)
    lines = runtime.profile.event_store.path.read_text(encoding='utf-8').strip().splitlines()
    assert any('"stage": "evaluate"' in line for line in lines)
    assert any('"stage": "outcome"' in line for line in lines)

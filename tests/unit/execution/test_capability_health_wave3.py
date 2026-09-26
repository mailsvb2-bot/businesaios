from __future__ import annotations

from execution.capability_health_policy import CapabilityHealthPolicy
from execution.capability_health_registry import CapabilityHealthRegistry
from execution.capability_health_scoring import FileCapabilityHealthStore
from execution.capability_matrix import CapabilityMatrix


def test_capability_policy_marks_stale_and_low_confidence() -> None:
    policy = CapabilityHealthPolicy()
    view = policy.build_view(
        counters={'attempts': 1, 'executed': 1, 'verified': 0, 'transient_failures': 0, 'terminal_failures': 0, 'blocked': 0},
        updated_at='2026-03-20T10:00:00Z',
        now_utc=__import__('datetime').datetime(2026, 3, 30, 12, 0, 0, tzinfo=__import__('datetime').timezone.utc),
    )
    assert view.staleness_state == 'stale'
    assert view.evidence_state == 'insufficient'
    assert view.recommended_autonomy_tier == 'autonomous_bounded'


def test_capability_registry_exposes_confidence_and_evidence_state(tmp_path) -> None:
    matrix = CapabilityMatrix()
    registry = CapabilityHealthRegistry(store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'), matrix=matrix)
    registry.update_after_feedback(
        tenant_id='tenant-1',
        action_type='notify_owner',
        feedback={'executed': True, 'verified': True, 'finished_at': '2026-03-30T18:00:00Z'},
    )
    payload = registry.runtime_payload_for_action(tenant_id='tenant-1', action_type='notify_owner')
    assert payload['confidence_score'] > 0.0
    assert payload['evidence_state'] in {'insufficient', 'sufficient'}
    assert payload['recommended_autonomy_tier'] in {'autonomous_bounded', 'supervised'}



def test_runtime_snapshot_keeps_bootstrap_evidence_below_full_autonomy() -> None:
    snapshot = CapabilityMatrix().record_for_action(
        action_type='launch_campaign',
        runtime_capabilities={
            'launch_campaign': {
                'healthy': True,
                'enabled': True,
                'observation_count': 0,
                'evidence_state': 'unknown',
                'recommended_autonomy_tier': 'full_autonomy',
            }
        },
    ).runtime
    assert snapshot.evidence_state == 'insufficient'
    assert snapshot.recommended_autonomy_tier == 'autonomous_bounded'


def test_capability_policy_error_budget_forces_supervised_autonomy() -> None:
    policy = CapabilityHealthPolicy(error_budget_limit=1.0, transient_failure_weight=0.25)
    view = policy.build_view(
        counters={
            'attempts': 4,
            'executed': 1,
            'verified': 1,
            'transient_failures': 1,
            'terminal_failures': 1,
            'blocked': 0,
            'accumulated_risk': 0.0,
        },
        updated_at='2026-09-26T10:00:00Z',
        now_utc=__import__('datetime').datetime(2026, 9, 26, 10, 1, 0, tzinfo=__import__('datetime').timezone.utc),
    )
    assert view.error_budget_used == 1.25
    assert view.error_budget_exceeded is True
    assert view.recommended_autonomy_tier == 'supervised'
    assert view.routing_state == 'fallback_preferred'


def test_capability_registry_accumulates_only_explicit_risk_signals(tmp_path) -> None:
    registry = CapabilityHealthRegistry(
        store=FileCapabilityHealthStore(root_dir=tmp_path / 'health'),
        matrix=CapabilityMatrix(),
        policy=CapabilityHealthPolicy(risk_budget_limit=1.0),
    )
    first = registry.update_after_feedback(
        tenant_id='tenant-1',
        action_type='notify_owner',
        feedback={
            'executed': True,
            'verified': True,
            'risk_score': 0.6,
            'finished_at': '2026-09-26T10:00:00Z',
        },
    )
    assert first.snapshot.accumulated_risk == 0.6
    assert first.snapshot.risk_budget_exceeded is False

    second = registry.update_after_feedback(
        tenant_id='tenant-1',
        action_type='notify_owner',
        feedback={
            'executed': True,
            'verified': True,
            'risk_penalty': 0.5,
            'finished_at': '2026-09-26T10:01:00Z',
        },
    )
    assert second.snapshot.accumulated_risk == 1.1
    assert second.snapshot.risk_budget_exceeded is True
    payload = second.to_runtime_payload()
    assert payload['recommended_autonomy_tier'] == 'supervised'
    assert payload['routing_state'] == 'fallback_preferred'

    third = registry.update_after_feedback(
        tenant_id='tenant-1',
        action_type='notify_owner',
        feedback={
            'executed': True,
            'verified': True,
            'finished_at': '2026-09-26T10:02:00Z',
        },
    )
    assert third.snapshot.accumulated_risk == 1.1


def test_capability_health_v2_snapshot_loads_with_zero_phase7_budgets(tmp_path) -> None:
    store = FileCapabilityHealthStore(root_dir=tmp_path / 'health')
    path = store._path(tenant_id='tenant-1', capability_key='notify_owner')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"schema_version":2,"tenant_id":"tenant-1","capability_key":"notify_owner","counters":{"attempts":2,"executed":2,"verified":1}}',
        encoding='utf-8',
    )
    snapshot = store.load(tenant_id='tenant-1', capability_key='notify_owner')
    assert snapshot.schema_version == 2
    assert snapshot.counters.accumulated_risk == 0.0
    assert snapshot.error_budget_used == 0.0
    assert snapshot.risk_budget_exceeded is False

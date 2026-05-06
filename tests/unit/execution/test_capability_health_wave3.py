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
    assert view.recommended_autonomy_tier == 'bounded_autonomy'


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
    assert payload['recommended_autonomy_tier'] in {'bounded_autonomy', 'full_autonomy', 'supervised'}



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
    assert snapshot.recommended_autonomy_tier == 'bounded_autonomy'

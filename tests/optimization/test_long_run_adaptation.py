from __future__ import annotations

from execution.optimization.adaptive_optimizer import AdaptiveOptimizer
from execution.optimization.performance_profile_store import FilePerformanceProfileStore


def _feedback(*, decision_id: str, correlation_id: str, route_key: str, executed: bool, verified: bool, achieved: bool, cost: float, revenue_delta: float, verification_confidence: float, latency_ms: float = 800.0, tenant_id: str = 'tenant-1', business_id: str = 'business-1', capability_key: str = 'launch_campaign') -> dict[str, object]:
    return {
        'tenant_id': tenant_id,
        'business_id': business_id,
        'capability_key': capability_key,
        'route_key': route_key,
        'action_type': 'launch_campaign',
        'decision_id': decision_id,
        'correlation_id': correlation_id,
        'executed': executed,
        'verified': verified,
        'achieved': achieved,
        'verification_confidence': verification_confidence,
        'latency_ms': latency_ms,
        'external_refs': [f'proof://{decision_id}'],
        'economic': {'cost': cost, 'revenue_delta': revenue_delta},
        'thresholds': {'before': 0.60, 'after': 0.60},
    }


def test_long_run_adaptation_improves_stronger_route_weight(tmp_path) -> None:
    optimizer = AdaptiveOptimizer(store=FilePerformanceProfileStore(root_dir=tmp_path / 'adaptive_profiles'))
    for index in range(12):
        assert optimizer.update_from_feedback(feedback=_feedback(decision_id=f'a-{index}', correlation_id=f'corr-a-{index}', route_key='ads/google', executed=True, verified=True, achieved=True, cost=10.0, revenue_delta=35.0, verification_confidence=0.95)).accepted is True
    for index in range(12):
        assert optimizer.update_from_feedback(feedback=_feedback(decision_id=f'b-{index}', correlation_id=f'corr-b-{index}', route_key='ads/experimental', executed=True, verified=False, achieved=False, cost=18.0, revenue_delta=2.0, verification_confidence=0.70)).accepted is True
    policy = optimizer.load_runtime_policy(tenant_id='tenant-1', business_id='business-1', capability_key='launch_campaign')
    assert policy['adaptation_ready'] is True
    assert policy['routing_table']['ads/google'] > policy['routing_table']['ads/experimental']


def test_duplicate_feedback_is_rejected_even_after_profile_reload(tmp_path) -> None:
    store = FilePerformanceProfileStore(root_dir=tmp_path / 'adaptive_profiles')
    optimizer_a = AdaptiveOptimizer(store=store)
    first = optimizer_a.update_from_feedback(feedback=_feedback(decision_id='dup-1', correlation_id='corr-dup-1', route_key='ads/google', executed=True, verified=True, achieved=True, cost=10.0, revenue_delta=25.0, verification_confidence=0.95))
    assert first.accepted is True
    optimizer_b = AdaptiveOptimizer(store=store)
    second = optimizer_b.update_from_feedback(feedback=_feedback(decision_id='dup-1', correlation_id='corr-dup-1', route_key='ads/google', executed=True, verified=True, achieved=True, cost=10.0, revenue_delta=25.0, verification_confidence=0.95))
    assert second.accepted is False
    assert second.noise_reason == 'duplicate_feedback'

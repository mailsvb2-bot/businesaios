from __future__ import annotations

from execution.business_operating_memory import BusinessMemoryCompactor, BusinessMemoryPolicy, FileBusinessOperatingMemoryStore


def test_business_memory_compacts_low_confidence_noise(tmp_path) -> None:
    policy = BusinessMemoryPolicy(max_recent_runs=3, min_pattern_frequency=2)
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / 'memory', policy=policy, compactor=BusinessMemoryCompactor(policy=policy))
    store.remember_execution(tenant_id='tenant-1', business_id='biz-1', run_id='run-1', goal='grow pipeline', completed=False, stop_reason='execution_failed', final_feedback={'goal_score': 0.10, 'error': 'timeout'}, step_count=1, profile={}, constraints={}, signals=[{'type': 'lead_volume', 'name': 'weekly', 'value': 'low'}], meta={}, channel='headless', region='global', product_name='BusinesAIOS', recorded_at='2026-03-21T10:00:00Z')
    store.remember_execution(tenant_id='tenant-1', business_id='biz-1', run_id='run-2', goal='grow pipeline', completed=False, stop_reason='execution_failed', final_feedback={'goal_score': 0.20, 'error': 'timeout'}, step_count=1, profile={}, constraints={}, signals=[{'type': 'lead_volume', 'name': 'weekly', 'value': 'low'}], meta={}, channel='headless', region='global', product_name='BusinesAIOS', recorded_at='2026-03-21T11:00:00Z')
    loaded = store.load(tenant_id='tenant-1', business_id='biz-1')
    assert loaded.total_runs == 2
    assert len(loaded.recurring_failures) >= 1
    assert loaded.recurring_failures[0].key in {'timeout', 'execution_failed'}

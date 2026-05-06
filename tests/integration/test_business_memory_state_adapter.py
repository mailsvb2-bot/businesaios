from __future__ import annotations

from core.ai.world_state import WorldStateV1
from execution.business_memory_state_adapter import BusinessMemoryStateAdapter
from execution.business_operating_memory import FileBusinessOperatingMemoryStore


def test_business_memory_is_injected_into_world_state_as_evidence_only(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / 'memory')
    store.remember_execution(
        tenant_id='tenant-1',
        business_id='biz-1',
        run_id='run-1',
        goal='increase revenue',
        completed=True,
        stop_reason='goal_reached',
        final_feedback={'goal_score': 0.91, 'goal_reached': True, 'normalized_outcome': {'qualified_leads': '12'}},
        step_count=1,
        profile={'segment': 'services'},
        constraints={'budget_limit': '1000'},
        signals=[{'type': 'lead_volume', 'name': 'weekly', 'value': 'high'}],
        meta={'channel': 'headless', 'region': 'eu'},
        channel='headless',
        region='eu',
        product_name='BusinesAIOS',
        recorded_at='2026-03-21T10:00:00Z',
    )
    adapter = BusinessMemoryStateAdapter(store=store)
    state = WorldStateV1(schema_version=1, user={'user_id': 'u1'}, session={'channel': 'headless'}, product={'business_id': 'biz-1'}, economy={}, timestamp_ms=1, tenant_id='tenant-1', meta={'goal': 'increase revenue'}, behavior={'goal': 'increase revenue'})
    enriched = adapter.inject(world_state=state, tenant_id='tenant-1', business_id='biz-1')
    memory = dict(enriched.meta['business_memory_evidence'])
    assert memory['evidence_only'] is True
    assert memory['must_not_issue_decision'] is True
    assert memory['must_not_unlock_effects'] is True
    assert memory['total_runs'] == 1
    assert enriched.meta['business_memory_summary']['business_profile'] == {'segment': 'services', 'channel': 'headless', 'region': 'eu'}

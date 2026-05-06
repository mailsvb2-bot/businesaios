from __future__ import annotations

from execution.market_intelligence_advanced_pipeline import MarketIntelligenceAdvancedPipeline
from execution.market_intelligence_advanced_models import HumanFeedbackEvent
from execution.market_intelligence_tenant_isolation import TenantIntelligenceScope


def test_advanced_pipeline_processes_records_and_builds_bridges(tmp_path):
    pipeline = MarketIntelligenceAdvancedPipeline()
    pipeline.incremental_sync.cursor_store.root_dir = tmp_path / 'cursor'
    pipeline.trend_engine.store.root_dir = tmp_path / 'trend'
    pipeline.feedback_loop.store.root_dir = tmp_path / 'feedback'
    result = pipeline.process_records(
        tenant_id='tenant-a',
        provider='amazon',
        source_family='marketplace',
        scope_key='scope-1',
        tenant_scope=TenantIntelligenceScope(tenant_id='tenant-a', allowed_providers=('amazon',), allowed_source_families=('marketplace',), max_records_per_sync=10),
        records=[
            {'title': 'Growth Widget', 'external_id': 'gw-1', 'url': 'https://example.com/a', 'review_count': 12, 'rating': 4.8},
            {'title': 'Growth Widget', 'external_id': 'gw-1', 'url': 'https://example.com/a', 'review_count': 12, 'rating': 4.8},
            {'title': 'Growth Widget Pro', 'external_id': 'gw-2', 'url': 'https://example.com/b', 'review_count': 130, 'rating': 4.9, 'engagement': 1500},
        ],
    )
    assert result['quality_report']['kept_rows'] == 2
    assert result['scores']
    assert 'market_intelligence_advanced' in result['world_state_patch']
    assert 'market_intelligence_advanced' in result['memory_payload']


def test_feedback_summary_round_trip(tmp_path):
    pipeline = MarketIntelligenceAdvancedPipeline()
    pipeline.feedback_loop.store.root_dir = tmp_path / 'feedback'
    pipeline.feedback_loop.record(HumanFeedbackEvent(tenant_id='tenant-a', entity_id='gw-1', label='validated', score_delta=0.3, tags=('gold',)))
    summary = pipeline.feedback_summary(tenant_id='tenant-a', entity_id='gw-1')
    assert summary['events_count'] == 1
    assert summary['tags'] == ['gold']

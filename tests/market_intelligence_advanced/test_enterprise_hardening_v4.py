from __future__ import annotations

from pathlib import Path

from execution.market_intelligence_data_quality import DataQualityGuard
from execution.market_intelligence_incremental_sync import IncrementalSyncEngine
from execution.market_intelligence_trend_engine import FileTrendStore, TemporalTrendEngine
from runtime._internal.market_intelligence.http_transport import HttpRequest
from runtime._internal.market_intelligence.provider_clients import MarketIntelligenceProviderClient, ProviderPlanRegistry, ProviderRequestPlan


def test_build_url_preserves_existing_query_and_repeated_params() -> None:
    req = HttpRequest(method='GET', url='https://example.test/search?lang=en', params={'tag': ['a', 'b'], 'page': 2})
    built = req.build_url()
    assert 'lang=en' in built
    assert built.count('tag=') == 2
    assert 'page=2' in built


def test_provider_client_supports_list_json_payload(tmp_path: Path) -> None:
    class FakeTransport:
        def execute(self, provider, req):
            return type('Resp', (), {'status_code': 200, 'json_payload': ({'id': '1', 'title': 'A'}, {'id': '2', 'title': 'B'})})()

    registry = ProviderPlanRegistry()
    registry.register(provider='demo', source_family='search', operation='scan', builder=lambda payload: ProviderRequestPlan(provider='demo', source_family='search', operation='scan', url='https://example.test/x', item_path='$', next_cursor_path='next'))
    client = MarketIntelligenceProviderClient(transport=FakeTransport(), plan_registry=registry)
    client.cursor_store.root_dir = tmp_path / 'cursors'
    result = client.execute_market_intelligence(provider='demo', source_family='search', operation='scan', payload={'tenant_id': 't1'}, dry_run=False)
    assert result['ok'] is True
    assert len(result['records']) == 2


def test_incremental_sync_preserves_history_across_partial_windows(tmp_path: Path) -> None:
    engine = IncrementalSyncEngine()
    engine.cursor_store.root_dir = tmp_path / 'cursors'
    first = engine.diff(tenant_id='t1', provider='p1', source_family='reviews', scope_key='s1', records=[{'id': '1', 'title': 'A'}, {'id': '2', 'title': 'B'}])
    second = engine.diff(tenant_id='t1', provider='p1', source_family='reviews', scope_key='s1', records=[{'id': '2', 'title': 'B2'}])
    assert len(first.cursor.metadata['seen_record_ids']) == 2
    assert set(second.cursor.metadata['seen_record_ids']) == {'1', '2'}
    assert len(second.changed_records) == 1


def test_data_quality_normalizes_url_and_review_count() -> None:
    rows, report = DataQualityGuard().process([{'title': 'Valid Product', 'url': 'HTTPS://Example.com/Path#frag', 'review_count': '7.8'}])
    assert report.kept_rows == 1
    assert rows[0]['url'] == 'https://example.com/Path'
    assert rows[0]['review_count'] == 7


def test_trend_store_sorts_points_by_timestamp(tmp_path: Path) -> None:
    store = FileTrendStore(root_dir=tmp_path / 'trends')
    engine = TemporalTrendEngine(store=store)
    engine.observe(type('Point', (), {'tenant_id': 't1', 'entity_id': 'e1', 'metric': 'demand', 'value': 30.0, 'observed_at': '2026-04-08T03:00:00+00:00', 'metadata': {}})())
    engine.observe(type('Point', (), {'tenant_id': 't1', 'entity_id': 'e1', 'metric': 'demand', 'value': 10.0, 'observed_at': '2026-04-08T01:00:00+00:00', 'metadata': {}})())
    summary = engine.summarize(tenant_id='t1', entity_id='e1', metric='demand')
    assert summary.latest_value == 30.0
    assert summary.slope > 0


def test_provider_scope_key_is_hashed_when_too_long(tmp_path: Path) -> None:
    registry = ProviderPlanRegistry()
    registry.register(provider='demo', source_family='search', operation='scan', builder=lambda payload: ProviderRequestPlan(provider='demo', source_family='search', operation='scan', url='https://example.test/x'))
    client = MarketIntelligenceProviderClient(plan_registry=registry)
    client.cursor_store.root_dir = tmp_path / 'cursors'
    long_query = 'x' * 500
    result = client.execute_market_intelligence(provider='demo', source_family='search', operation='scan', payload={'tenant_id': 't1', 'query': long_query}, dry_run=True)
    assert len(result['cursor']['scope_key']) == 64

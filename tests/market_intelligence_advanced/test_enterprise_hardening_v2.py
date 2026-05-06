from __future__ import annotations

from execution.market_intelligence_data_quality import DataQualityGuard
from execution.market_intelligence_incremental_sync import IncrementalSyncEngine
from runtime._internal.market_intelligence.http_transport import HttpRequest, HttpTransportError
from runtime._internal.market_intelligence.pagination import PageCursor, PageResult, PaginationWindow


def test_incremental_sync_persists_record_identity_cursor(tmp_path):
    engine = IncrementalSyncEngine()
    engine.cursor_store.root_dir = tmp_path
    diff = engine.diff(
        tenant_id='t1',
        provider='amazon',
        source_family='marketplace',
        scope_key='phones',
        records=({'id': 'sku-1', 'title': 'Phone X', 'updated_at': '2026-01-01T00:00:00+00:00'},),
    )
    assert diff.cursor.cursor == 'sku-1'
    assert diff.cursor.last_seen_at == '2026-01-01T00:00:00+00:00'


def test_data_quality_flags_spam_and_clamps_values():
    guard = DataQualityGuard()
    rows, report = guard.process([
        {'title': 'aaaaaaa', 'rating': 999, 'price': -50},
        {'title': 'Useful product', 'rating': 7, 'price': -10, 'review_count': -2},
    ])
    assert report.dropped_noise == 1
    assert rows[0]['rating'] == 5.0
    assert rows[0]['price'] == 0.0
    assert rows[0]['review_count'] == 0.0


def test_pagination_summary_returns_final_cursor():
    window = PaginationWindow(max_pages=3, max_items=10)
    calls = []
    def fetch(cursor):
        calls.append(cursor.token if cursor else None)
        if not cursor:
            return PageResult(items=({'id': '1'},), next_cursor=PageCursor(token='next-1', page_number=2), metadata={'page': 1})
        return PageResult(items=({'id': '2'},), exhausted=True, metadata={'page': 2})
    summary = window.collect_summary(fetch)
    assert len(summary.rows) == 2
    assert summary.final_cursor_token == 'next-1'
    assert summary.pages_fetched == 2


def test_http_request_rejects_non_http_scheme():
    from runtime._internal.market_intelligence.http_transport import CanonicalHttpTransport
    transport = CanonicalHttpTransport()
    try:
        transport.execute('test', HttpRequest(method='GET', url='file:///etc/passwd'))
    except HttpTransportError as exc:
        assert exc.code == 'invalid_request'
    else:
        raise AssertionError('expected invalid_request')

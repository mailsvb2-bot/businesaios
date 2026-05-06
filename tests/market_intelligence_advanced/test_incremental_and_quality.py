from execution.market_intelligence_data_quality import DataQualityGuard
from execution.market_intelligence_incremental_sync import IncrementalSyncEngine
from runtime._internal.market_intelligence.cursor_store import FileProviderCursorStore


def test_incremental_sync_detects_new_and_changed(tmp_path):
    engine = IncrementalSyncEngine(cursor_store=FileProviderCursorStore(root_dir=tmp_path / 'cursors'))
    first = engine.diff(
        tenant_id='t1', provider='amazon', source_family='marketplace', scope_key='query:crm',
        records=({'id': '1', 'title': 'CRM tool', 'price': 10}, {'id': '2', 'title': 'ERP tool', 'price': 20}),
    )
    assert len(first.new_records) == 2
    second = engine.diff(
        tenant_id='t1', provider='amazon', source_family='marketplace', scope_key='query:crm',
        records=({'id': '1', 'title': 'CRM tool', 'price': 12}, {'id': '2', 'title': 'ERP tool', 'price': 20}),
    )
    assert len(second.changed_records) == 1
    assert len(second.unchanged_records) == 1


def test_data_quality_guard_drops_noise_and_duplicates():
    guard = DataQualityGuard()
    kept, report = guard.process([
        {'id': '1', 'title': 'Great CRM'},
        {'id': '1', 'title': 'Great CRM'},
        {'id': '2', 'title': 'n/a'},
    ])
    assert len(kept) == 1
    assert report.dropped_duplicates == 1
    assert report.dropped_noise == 1

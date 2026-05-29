from __future__ import annotations

from datetime import datetime, timezone, UTC

from runtime.queue.queue_remediation_route_history_sqlite import SqliteQueueRemediationRouteHistoryStore


def test_queue_remediation_route_history_store_records_entries(tmp_path):
    store = SqliteQueueRemediationRouteHistoryStore(path=tmp_path / 'route_history.sqlite3')
    entry = store.record(
        tenant_id='tenant-a',
        queue_name='ops',
        action='execute_remediation_hook',
        source='control_plane',
        status='executed',
        actor_id='operator-1',
        request_id='req-1',
        metadata={'hook_code': 'refresh_health_sample'},
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert entry.action == 'execute_remediation_hook'
    rows = store.list_entries(tenant_id='tenant-a', queue_name='ops')
    assert len(rows) == 1
    assert rows[0].actor_id == 'operator-1'
    assert rows[0].metadata['hook_code'] == 'refresh_health_sample'

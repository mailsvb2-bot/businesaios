from __future__ import annotations

from entrypoints.api.analytics_models import AnalyticsMaterializeRequest, AnalyticsQueueMaterializeRequest, AnalyticsSnapshotReadRequest, AnalyticsSnapshotWriteRequest
from entrypoints.api.analytics_ops_route_handlers import AnalyticsOpsRouteHandlers
from entrypoints.api.analytics_route_handlers import AnalyticsRouteHandlers
from application.analytics.fleet_queue_job_bridge import AnalyticsFleetQueueJobBridge
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_store import InMemoryJobStore


class _EventStore:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id, start_ms, end_ms=None, event_type=None):
        for item in self._events:
            if str(item.get('tenant_id') or 'default') != str(tenant_id):
                continue
            if event_type is not None and str(item.get('event_type') or '') != str(event_type):
                continue
            yield dict(item)


def test_analytics_route_handlers_roundtrip(tmp_path):
    events = [
        {'tenant_id': 'tenant-1', 'event_type': 'offer_shown', 'user_id': 'u1', 'timestamp_ms': 1, 'payload': {}},
        {'tenant_id': 'tenant-1', 'event_type': 'offer_clicked', 'user_id': 'u1', 'timestamp_ms': 2, 'payload': {}},
        {'tenant_id': 'tenant-1', 'event_type': 'purchase_success', 'user_id': 'u1', 'timestamp_ms': 3, 'payload': {'amount': 10.0}},
        {'tenant_id': 'tenant-1', 'event_type': 'decision_issued', 'user_id': 'u1', 'timestamp_ms': 4, 'payload': {}},
        {'tenant_id': 'tenant-1', 'event_type': 'decision_executed', 'user_id': 'u1', 'timestamp_ms': 5, 'payload': {}},
        {'tenant_id': 'tenant-1', 'event_type': 'latency_span', 'user_id': 'u1', 'timestamp_ms': 6, 'payload': {'duration_ms': 300}},
    ]
    handlers = AnalyticsRouteHandlers(event_store=_EventStore(events), snapshot_db_path=str(tmp_path / 'snap.sqlite3'))
    dashboard = handlers.get_dashboard_bundle(tenant_id='tenant-1', window_days=30)
    assert dashboard['payload']['dashboard']['tenant_id'] == 'tenant-1'
    write_payload = handlers.write_snapshot(AnalyticsSnapshotWriteRequest(tenant_id='tenant-1', snapshot_kind='dashboard', payload=dashboard['payload']))
    read_payload = handlers.read_snapshot(AnalyticsSnapshotReadRequest(snapshot_id=write_payload['snapshot_id']))
    assert read_payload['tenant_id'] == 'tenant-1'


def test_analytics_ops_handlers_materialize_and_enqueue(tmp_path):
    events = [
        {'tenant_id': 'tenant-1', 'event_type': 'offer_shown', 'user_id': 'u1', 'timestamp_ms': 1, 'payload': {}},
        {'tenant_id': 'tenant-1', 'event_type': 'latency_span', 'user_id': 'u1', 'timestamp_ms': 2, 'payload': {'duration_ms': 100}},
    ]
    bridge = AnalyticsFleetQueueJobBridge(dispatcher=JobDispatcher(store=InMemoryJobStore()))
    ops = AnalyticsOpsRouteHandlers(event_store=_EventStore(events), snapshot_db_path=str(tmp_path / 'snap.sqlite3'), queue_bridge=bridge)
    result = ops.materialize_bundle(AnalyticsMaterializeRequest(tenant_id='tenant-1', window_days=7))
    enqueue = ops.enqueue_materialization(AnalyticsQueueMaterializeRequest(tenant_id='tenant-1', window_days=7))
    assert result['tenant_id'] == 'tenant-1'
    assert enqueue['accepted'] is True

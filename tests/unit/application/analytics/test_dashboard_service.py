from __future__ import annotations

from application.analytics.dashboard_service import ApplicationAnalyticsDashboardService


class _EventStore:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id, start_ms, end_ms=None, event_type=None):
        for item in self._events:
            if str(item.get('tenant_id') or 'default') != str(tenant_id):
                continue
            yield dict(item)


def test_dashboard_service_builds_bundle():
    service = ApplicationAnalyticsDashboardService(
        event_store=_EventStore([
            {'tenant_id': 'tenant-1', 'event_type': 'offer_shown', 'user_id': 'u1', 'timestamp_ms': 1, 'payload': {}},
            {'tenant_id': 'tenant-1', 'event_type': 'offer_clicked', 'user_id': 'u1', 'timestamp_ms': 2, 'payload': {}},
            {'tenant_id': 'tenant-1', 'event_type': 'purchase_success', 'user_id': 'u1', 'timestamp_ms': 3, 'payload': {'amount': 20.0}},
            {'tenant_id': 'tenant-1', 'event_type': 'decision_issued', 'user_id': 'u1', 'timestamp_ms': 4, 'payload': {}},
            {'tenant_id': 'tenant-1', 'event_type': 'decision_executed', 'user_id': 'u1', 'timestamp_ms': 5, 'payload': {}},
            {'tenant_id': 'tenant-1', 'event_type': 'latency_span', 'user_id': 'u1', 'timestamp_ms': 6, 'payload': {'duration_ms': 500}},
        ])
    )
    bundle = service.build_dashboard_bundle(tenant_id='tenant-1', window_days=30)
    assert 'dashboard' in bundle
    assert 'explainability' in bundle
    assert 'tenant_rollup' in bundle

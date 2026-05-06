from __future__ import annotations

from application.analytics.fleet_analytics_coordinator import FleetAnalyticsCoordinator


class _EventStore:
    def __init__(self, tenant_id: str):
        self._tenant_id = tenant_id

    def iter_events(self, *, tenant_id, start_ms, end_ms=None, event_type=None):
        assert str(tenant_id) == self._tenant_id
        yield {'tenant_id': tenant_id, 'event_type': 'offer_shown', 'user_id': 'u1', 'timestamp_ms': 1, 'payload': {}}
        yield {'tenant_id': tenant_id, 'event_type': 'offer_clicked', 'user_id': 'u1', 'timestamp_ms': 2, 'payload': {}}
        yield {'tenant_id': tenant_id, 'event_type': 'purchase_success', 'user_id': 'u1', 'timestamp_ms': 3, 'payload': {'amount': 10.0}}
        yield {'tenant_id': tenant_id, 'event_type': 'decision_issued', 'user_id': 'u1', 'timestamp_ms': 4, 'payload': {}}
        yield {'tenant_id': tenant_id, 'event_type': 'decision_executed', 'user_id': 'u1', 'timestamp_ms': 5, 'payload': {}}
        yield {'tenant_id': tenant_id, 'event_type': 'latency_span', 'user_id': 'u1', 'timestamp_ms': 6, 'payload': {'duration_ms': 500}}


def test_fleet_analytics_coordinator_builds_rollup():
    coordinator = FleetAnalyticsCoordinator(event_store_factory=lambda tenant_id: _EventStore(tenant_id))
    payload = coordinator.build_fleet_rollup(tenant_ids=['tenant-a', 'tenant-b'], window_days=30)
    assert payload['tenant_count'] == 2
    assert payload['healthy_tenants'] >= 1

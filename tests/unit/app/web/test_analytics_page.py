from __future__ import annotations

from app.web.pages.analytics import AnalyticsPage


class _EventStore:
    def __init__(self, events):
        self._events = list(events)

    def iter_events(self, *, tenant_id, start_ms, end_ms=None, event_type=None):
        for item in self._events:
            if str(item.get('tenant_id') or 'default') != str(tenant_id):
                continue
            yield dict(item)


def test_analytics_page_builds_payload():
    page = AnalyticsPage()
    payload = page.build(
        event_store=_EventStore([
            {'tenant_id': 'tenant-1', 'event_type': 'offer_shown', 'user_id': 'u1', 'timestamp_ms': 1, 'payload': {}},
            {'tenant_id': 'tenant-1', 'event_type': 'offer_clicked', 'user_id': 'u1', 'timestamp_ms': 2, 'payload': {}},
            {'tenant_id': 'tenant-1', 'event_type': 'purchase_success', 'user_id': 'u1', 'timestamp_ms': 3, 'payload': {'amount': 12.0}},
        ]),
        tenant_id='tenant-1',
        window_days=30,
    )
    assert payload['kind'] == 'analytics_page'
    assert payload['payload']['tenant_id'] == 'tenant-1'

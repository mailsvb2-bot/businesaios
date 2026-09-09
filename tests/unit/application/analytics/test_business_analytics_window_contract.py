from application.analytics.business_analytics_service import ApplicationBusinessAnalyticsService


class _EventStore:
    def __init__(self, events):
        self.events, self.calls = events, []

    def iter_events(self, *, tenant_id, start_ms=0, end_ms=None):
        self.calls.append((tenant_id, start_ms, end_ms))
        return [event for event in self.events if start_ms <= int(event['timestamp_ms']) <= int(end_ms)]


def test_default_business_analytics_window_is_really_last_30_days(monkeypatch):
    now_ms = 2_000_000_000_000
    day_ms = 24 * 3600 * 1000
    store = _EventStore([
        {'event_type': 'purchase_success', 'user_id': 'old', 'timestamp_ms': now_ms - 31 * day_ms, 'payload': {'amount': 90}},
        {'event_type': 'purchase_success', 'user_id': 'new', 'timestamp_ms': now_ms - day_ms, 'payload': {'amount': 10}},
    ])
    monkeypatch.setattr('application.analytics.business_analytics_service.time.time', lambda: now_ms / 1000)
    scorecard = ApplicationBusinessAnalyticsService(event_store=store).build_scorecard(tenant_id='tenant-a', window_days=30)
    assert store.calls == [('tenant-a', now_ms - 30 * day_ms, now_ms)]
    assert scorecard.generated_at_ms == now_ms
    assert scorecard.revenue.purchase_success_count == 1
    assert scorecard.revenue.revenue_total == 10.0


def test_business_analytics_rejects_non_positive_or_unbounded_windows():
    service = ApplicationBusinessAnalyticsService(event_store=_EventStore([]))
    for days in (0, -1, 3651):
        try:
            service.build_scorecard(tenant_id='tenant-a', window_days=days, now_ms=2_000_000_000_000)
        except ValueError as exc:
            assert str(exc) == 'window_days must be between 1 and 3650'
        else:
            raise AssertionError(f'window_days={days} must be rejected')

from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.notification_planner import AlertNotificationPlanner
from runtime.messaging_policy_alert_subscriptions.service import MessagingPolicyAlertSubscriptionService
from runtime.messaging_policy_alert_subscriptions.subscription_loader import load_alert_subscriptions
from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_events.event_store_adapter import EventLogMessagingPolicyEventStore
from runtime.messaging_policy_readmodel.read_api import read_messaging_policy_snapshot
from runtime.messaging_policy_trace.search_service import MessagingPolicyTraceSearchService


class _SettingsGateway:
    def __init__(self):
        self.calls = []

    def get_value(self, *, tenant_id, key):
        self.calls.append((tenant_id, key))
        return []


class _AlertService:
    def __init__(self):
        self.calls = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return type('AlertResult', (), {'alerts': ()})()


class _Notifier:
    def notify(self, **kwargs):
        return type('NotifyResult', (), {'notifications_total': 0, 'notifications_sent': 0, 'notifications_suppressed': 0})()


class _ReadService:
    def __init__(self):
        self.calls = []

    def get_snapshot(self, **kwargs):
        self.calls.append(kwargs)
        return {'tenant_id': 'default', 'user_id': 'u1', 'correlation_id': 'c1'}


class _SearchStore:
    def __init__(self):
        self.calls = []

    def search_records(self, **kwargs):
        self.calls.append(kwargs)
        return []


class _EventLog:
    def __init__(self):
        self.emitted = []
        self.items = []

    def emit(self, **kwargs):
        self.emitted.append(kwargs)

    def iter_events(self):
        return list(self.items)


def test_subscription_loader_normalizes_placeholder_tenant_to_unknown():
    gw = _SettingsGateway()
    load_alert_subscriptions(settings_gateway=gw, tenant_id='default')
    assert gw.calls[0][0] == 'unknown_tenant'


def test_alert_subscription_service_uses_normalized_tenant_scope_everywhere():
    alert_service = _AlertService()
    service = MessagingPolicyAlertSubscriptionService(alert_service=alert_service, notifier=_Notifier())
    gw = _SettingsGateway()
    out = service.run(settings_gateway=gw, effects=None, tenant_id='legacy', decision_id='d1', correlation_id='c1')
    assert out['alerts_count'] == 0
    assert alert_service.calls[0]['tenant_id'] == 'unknown_tenant'
    assert gw.calls[0][0] == 'unknown_tenant'


def test_notification_planner_normalizes_placeholder_tenant():
    planner = AlertNotificationPlanner()
    alert = type('Alert', (), {'code': 'a1', 'level': 'warn', 'title': 'T', 'detail': 'D', 'metric_name': '', 'metric_value': '', 'threshold_value': ''})()
    sub = type('Sub', (), {'recipient_user_id': 'u2', 'channel': 'telegram', 'alert_code': 'a1', 'alert_level': 'warn', 'affected_user_id': 'u3'})()
    match_service = type('Match', (), {'match': lambda self, **kwargs: (sub,)})()
    plan = planner.build_plan(tenant_id='default', affected_user_id='u3', alerts=(alert,), subscriptions=(sub,), date_from='', date_to='', match_service=match_service)
    assert plan.items[0].tenant_id == 'unknown_tenant'
    assert 'tenant_id=unknown_tenant' in plan.items[0].text


def test_event_factory_and_store_normalize_placeholder_tenant():
    record = build_event(tenant_id='default', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_policy_plan_created')
    assert record.tenant_id == 'unknown_tenant'
    log = _EventLog()
    store = EventLogMessagingPolicyEventStore(event_log=log)
    store.append(record)
    assert log.emitted[0]['payload']['tenant_id'] == 'unknown_tenant'
    log.items = [
        {
            'event_type': 'messaging_policy_plan_created',
            'payload': {'tenant_id': 'default'},
            'user_id': 'u1',
            'decision_id': 'd1',
            'correlation_id': 'c1',
            'source': 'messaging_policy',
            'timestamp_ms': 1,
            'event_id': 'e1',
        }
    ]
    items = store.read(tenant_id='legacy', user_id='u1', correlation_id='c1')
    assert len(items) == 1
    assert items[0].tenant_id == 'unknown_tenant'


def test_read_api_and_trace_search_normalize_placeholder_tenant():
    read_service = _ReadService()
    snap = read_messaging_policy_snapshot(read_service=read_service, tenant_id='default', user_id='u1', correlation_id='c1')
    assert read_service.calls[0]['tenant_id'] == 'unknown_tenant'
    assert snap['tenant_id'] == 'unknown_tenant'

    search_store = _SearchStore()
    service = MessagingPolicyTraceSearchService(search_store=search_store)
    service.search(tenant_id='default', user_id='u1')
    assert search_store.calls[0]['tenant_id'] == 'unknown_tenant'

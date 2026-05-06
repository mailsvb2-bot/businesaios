from core.events.log import EventLog
from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_events.event_store_adapter import EventLogMessagingPolicyEventStore
from runtime.messaging_policy_readmodel.boot_dependencies import build_messaging_policy_read_services


class _RawEventStore(list):
    def append_event(self, event: dict):
        self.append(dict(event))

    def iter_events(self, *, tenant_id: str, start_ms: int = 0, end_ms: int | None = None, user_id: str | None = None, event_type: str | None = None):
        end = (2**63 - 1) if end_ms is None else int(end_ms)
        for event in list(self):
            if str(event.get('tenant_id') or '') != str(tenant_id):
                continue
            ts = int(event.get('timestamp_ms') or 0)
            if ts < int(start_ms) or ts >= end:
                continue
            if user_id is not None and str(event.get('user_id') or '') != str(user_id):
                continue
            if event_type is not None and str(event.get('event_type') or '') != str(event_type):
                continue
            yield dict(event)


def test_read_service_rebuilds_from_event_store_when_snapshot_missing():
    raw = _RawEventStore()
    event_log = EventLog(raw, tenant='t1')
    event_store = EventLogMessagingPolicyEventStore(event_log=event_log)
    event_store.append(build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_policy_plan_created', payload={'ordered_channels': ['telegram', 'email']}))
    event_store.append(build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_message_delivered', payload={'channel': 'email'}))
    event_store.append(build_event(tenant_id='t1', user_id='u1', decision_id='d1', correlation_id='c1', event_type='messaging_policy_execution_finished', payload={'selected_channel': 'email', 'terminal_reason': '', 'attempts_count': 1}))

    services = build_messaging_policy_read_services(event_store=event_store)
    snap = services['read_service'].get_snapshot(tenant_id='t1', user_id='u1', correlation_id='c1')

    assert snap is not None
    assert snap.last_selected_channel == 'email'
    assert snap.delivered == ('email',)

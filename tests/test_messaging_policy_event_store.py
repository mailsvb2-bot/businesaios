from core.events.log import EventLog
from runtime.messaging_policy_events.event_factory import build_event
from runtime.messaging_policy_events.event_store_adapter import EventLogMessagingPolicyEventStore
from runtime.messaging_policy_events.inmemory_event_store import InMemoryMessagingPolicyEventStore


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


def test_inmemory_event_store_append_and_read():
    store = InMemoryMessagingPolicyEventStore()
    event = build_event(
        tenant_id='t1',
        user_id='u1',
        decision_id='d1',
        correlation_id='c1',
        event_type='messaging_message_attempted',
        payload={'channel': 'whatsapp'},
    )
    store.append(event)
    items = store.read(tenant_id='t1', user_id='u1', correlation_id='c1')
    assert len(items) == 1
    assert items[0].event_type == 'messaging_message_attempted'


def test_eventlog_adapter_reads_from_same_canonical_event_stream():
    raw = _RawEventStore()
    event_log = EventLog(raw, tenant='tenant-x')
    store = EventLogMessagingPolicyEventStore(event_log=event_log)
    store.append(
        build_event(
            tenant_id='tenant-x',
            user_id='u1',
            decision_id='d1',
            correlation_id='c1',
            event_type='messaging_message_delivered',
            payload={'channel': 'sms'},
        )
    )
    items = store.read(tenant_id='tenant-x', user_id='u1', correlation_id='c1')
    assert len(items) == 1
    assert items[0].payload['channel'] == 'sms'
    assert len(raw) == 1

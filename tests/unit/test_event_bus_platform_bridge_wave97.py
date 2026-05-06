from observability.event_bus import EventBus as ObservabilityEventBus
from observability.events import Event
from runtime.platform.support.events.event_bus import EventBus as RuntimeEventBus


def test_observability_event_bus_preserves_record_and_subscription_behavior() -> None:
    bus = ObservabilityEventBus()
    seen = []

    bus.subscribe('decision.published', lambda event: seen.append(event.event_id))
    event = Event('decision.published', {'approved': True})
    bus.publish(event)

    assert bus.events[-1].event_id == event.event_id
    assert seen == [event.event_id]
    assert bus.events_for_type('decision.published')[0].event_id == event.event_id


def test_runtime_event_bus_uses_append_only_topic_log_without_changing_payload_copy_semantics() -> None:
    bus = RuntimeEventBus()
    payload = {'kind': 'ready'}

    bus.publish('runtime.ready', payload)
    payload['kind'] = 'mutated'

    assert bus.events('runtime.ready') == [{'kind': 'ready'}]

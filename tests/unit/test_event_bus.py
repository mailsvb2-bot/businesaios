from observability.event_bus import EventBus
from observability.events import Event


def test_event_bus_records_and_fanouts_events():
    bus = EventBus()
    seen = []
    bus.subscribe('decision.published', lambda event: seen.append(event.event_id))
    event = Event('decision.published', {'approved': True})
    bus.publish(event)
    assert bus.events[-1].event_id == event.event_id
    assert seen == [event.event_id]

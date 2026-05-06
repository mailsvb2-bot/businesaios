from observability.demand import emit_demand_events as emit_demand_event
from observability.demand import emit_delivery_events as emit_delivery_event


class _Log(list):
    def emit(self, **event) -> None:
        self.append(event)


def test_typed_emitters_preserve_stream_identity() -> None:
    log = _Log()
    emit_demand_event(log, 'request_received', {'request_id': 'r1'})
    emit_delivery_event(log, 'lead_sent', {'request_id': 'r1'})

    assert log[0]['event_type'] == 'demand_events'
    assert log[1]['event_type'] == 'delivery_events'
    assert log[0]['payload']['name'] == 'request_received'
    assert log[1]['payload']['name'] == 'lead_sent'

from contracts.demand import ClientRequest
from contracts.matching.routing_decision import RoutingDecision
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher


class _StubAdapter:
    CHANNEL = 'crm'

    def deliver(self, *, request, decision):
        return {
            'status': 'accepted',
            'detail': 'transport_not_configured',
            'stub': True,
            'stub_detail': 'adapter_stub_dispatched',
        }


class _Recorder:
    def __init__(self):
        self.calls = []

    def notify(self, **kwargs):
        self.calls.append(kwargs)

    def confirm(self, **kwargs):
        self.calls.append(kwargs)


class _EventLog:
    def __init__(self):
        self.events = []

    def emit(self, **item):
        self.events.append(item)


class _Registry:
    def items(self):
        return (('crm', _StubAdapter()),)

    def get(self, name):
        return _StubAdapter()


class _Selector:
    def choose(self, **kwargs):
        return 'crm'


def test_stub_delivery_is_not_marked_delivered_and_skips_side_effect_notifiers() -> None:
    event_log = _EventLog()
    dispatcher = LeadDeliveryDispatcher(event_log=event_log)
    dispatcher._registry = _Registry()
    dispatcher._selector = _Selector()
    dispatcher._biz_notify = _Recorder()
    dispatcher._cust_confirm = _Recorder()

    request = ClientRequest(request_id='r1', text='hi', channel='web', customer_id='c1')
    decision = RoutingDecision(
        request_id='r1',
        selected_business_id='biz-1',
        trace={'decision_path': 'core.ai.decision_core', 'optimization_target': 'route_quality_and_business_value', 'request_id': 'r1'},
        requires_manual_review=False,
    )
    outcome = dispatcher.dispatch(request=request, decision=decision)

    assert outcome is not None
    assert outcome.delivery_status == 'accepted'
    assert outcome.delivered_at_ms is None
    assert dispatcher._biz_notify.calls == []
    assert dispatcher._cust_confirm.calls == []
    assert any(event['payload'].get('name') == 'delivery_transport_not_configured' for event in event_log.events)

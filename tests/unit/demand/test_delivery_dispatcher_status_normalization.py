from contracts.demand import ClientRequest
from contracts.matching.routing_decision import RoutingDecision
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher


class _Adapter:
    CHANNEL = 'crm'

    def deliver(self, *, request, decision):
        return {'status': 'ok', 'detail': 'stub'}


def test_delivery_dispatcher_normalizes_ok_to_delivered() -> None:
    dispatcher = LeadDeliveryDispatcher()
    dispatcher._registry = type('R', (), {'items': lambda self: (('crm', _Adapter()),), 'get': lambda self, name: _Adapter()})()
    request = ClientRequest(request_id='r1', text='hi', channel='web', customer_id='c1')
    decision = RoutingDecision(request_id='r1', selected_business_id='biz-1', trace={'decision_path': 'core.ai.decision_core', 'optimization_target': 'route_quality_and_business_value', 'request_id': 'r1'}, requires_manual_review=False)
    outcome = dispatcher.dispatch(request=request, decision=decision)
    assert outcome is not None
    assert outcome.delivery_status == 'delivered'

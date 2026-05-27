from contracts.demand import ClientRequest
from contracts.matching.routing_decision import RoutingDecision
from demand_os.outcome_recorder import DemandOutcomeRecorder
from lead_outcomes import LeadOutcomeRegistry
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher


class _Registry:
    def __init__(self, status: str):
        self._adapter = type('A', (), {'CHANNEL': 'crm', 'deliver': lambda self, *, request, decision: {'status': status, 'detail': status}})()

    def items(self):
        return (('crm', self._adapter),)

    def get(self, name):
        return self._adapter


class _Optimizer:
    def current_state(self):
        return {}

    def learn(self, rows):
        return {'seen': len(tuple(rows))}


def _request() -> ClientRequest:
    return ClientRequest(request_id='r1', text='hi', channel='web', customer_id='c1')


def _decision() -> RoutingDecision:
    return RoutingDecision(request_id='r1', selected_business_id='biz-1', trace={'decision_path': 'core.ai.decision_core', 'optimization_target': 'route_quality_and_business_value', 'request_id': 'r1'}, requires_manual_review=False)


def test_delivery_dispatcher_preserves_accepted_status() -> None:
    dispatcher = LeadDeliveryDispatcher()
    dispatcher._registry = _Registry('accepted')
    outcome = dispatcher.dispatch(request=_request(), decision=_decision())
    assert outcome is not None
    assert outcome.delivery_status == 'accepted'
    assert outcome.delivered_at_ms is None


def test_delivery_dispatcher_preserves_queued_status() -> None:
    dispatcher = LeadDeliveryDispatcher()
    dispatcher._registry = _Registry('queued')
    outcome = dispatcher.dispatch(request=_request(), decision=_decision())
    assert outcome is not None
    assert outcome.delivery_status == 'queued'
    assert outcome.delivered_at_ms is None


def test_outcome_seed_preserves_non_terminal_delivery_status() -> None:
    registry = LeadOutcomeRegistry()
    recorder = DemandOutcomeRecorder(outcomes=registry, optimizer=_Optimizer())
    recorder.seed(request=_request(), decision=_decision(), delivery=type('D', (), {'delivery_status': 'queued', 'channel': 'crm', 'delivered_at_ms': None})())
    assert registry.require('r1')['delivery_status'] == 'queued'
    assert registry.require('r1')['status'] == 'queued'

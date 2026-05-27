from contracts.demand import ClientIntent, ClientRequest, DemandFlowBundle
from contracts.matching.match_bundle import MatchBundle
from contracts.matching.routing_decision import RoutingDecision


def test_flow_bundle_as_dict_is_jsonable() -> None:
    bundle = DemandFlowBundle(
        request=ClientRequest(request_id='r1', text='hello', channel='web', customer_id='c1'),
        intent=ClientIntent(service_type='general', confidence=0.8),
        supply_profiles=(),
        live_states=(),
        gravity_snapshot={'vectors': {}},
        match_bundle=MatchBundle(request_id='r1', candidates=(), audit={}),
        routing_preparation={'request_id': 'r1', 'ranked_candidates': (), 'trace': {'request_id': 'r1'}, 'requires_manual_review': True},
        decision=RoutingDecision(request_id='r1', selected_business_id=None, trace={'decision_path': 'core.ai.decision_core'}, requires_manual_review=True),
        delivery=None,
    )
    payload = bundle.as_jsonable()
    assert payload['request']['request_id'] == 'r1'
    assert payload['intent']['service_type'] == 'general'

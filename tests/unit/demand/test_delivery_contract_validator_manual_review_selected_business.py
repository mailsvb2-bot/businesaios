from contracts.demand import ClientRequest
from contracts.matching.routing_decision import RoutingDecision
from routing_execution.delivery_contract_validator import DeliveryContractValidator


def test_delivery_contract_rejects_manual_review_with_selected_business() -> None:
    validator = DeliveryContractValidator()
    request = ClientRequest(request_id='r1')
    decision = RoutingDecision(
        request_id='r1',
        selected_business_id='biz-1',
        trace={'decision_path': 'core.ai.decision_core', 'optimization_target': 'route_quality_and_business_value', 'request_id': 'r1'},
        requires_manual_review=True,
    )
    try:
        validator.validate(request=request, decision=decision, channel='manual_review')
    except ValueError as exc:
        assert 'manual review decision cannot carry selected business' in str(exc)
    else:
        raise AssertionError('expected validation error')

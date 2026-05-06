import pytest

from contracts.matching.routing_decision import RoutingDecision
from routing_execution.delivery_contract_validator import DeliveryContractValidator
from config.execution_contract import CANONICAL_DECISION_PATH, CANONICAL_OPTIMIZATION_TARGET


class Request:
    request_id = 'req-1'


def test_delivery_validator_rejects_mismatched_trace_request_id() -> None:
    decision = RoutingDecision(
        request_id='req-1',
        selected_business_id='biz-1',
        runner_up_business_ids=('biz-2',),
        trace={'decision_path': CANONICAL_DECISION_PATH, 'optimization_target': CANONICAL_OPTIMIZATION_TARGET, 'request_id': 'req-2'},
        requires_manual_review=False,
    )
    with pytest.raises(ValueError):
        DeliveryContractValidator().validate(request=Request(), decision=decision, channel='crm')

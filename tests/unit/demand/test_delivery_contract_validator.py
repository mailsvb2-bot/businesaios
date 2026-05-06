from __future__ import annotations

import pytest

from config.execution_contract import CANONICAL_DECISION_PATH, CANONICAL_OPTIMIZATION_TARGET
from contracts.matching.routing_decision import RoutingDecision
from routing_execution.delivery_contract_validator import DeliveryContractValidator


class Request:
    request_id = 'r1'


def test_validator_accepts_canonical_decision_path() -> None:
    decision = RoutingDecision(
        request_id='r1',
        selected_business_id='biz-1',
        runner_up_business_ids=(),
        trace={'decision_path': CANONICAL_DECISION_PATH, 'optimization_target': CANONICAL_OPTIMIZATION_TARGET},
        requires_manual_review=False,
    )
    DeliveryContractValidator().validate(request=Request(), decision=decision, channel='crm')


def test_validator_rejects_legacy_decision_path() -> None:
    decision = RoutingDecision(
        request_id='r1',
        selected_business_id='biz-1',
        runner_up_business_ids=(),
        trace={'decision_path': 'demand_decision', 'optimization_target': CANONICAL_OPTIMIZATION_TARGET},
        requires_manual_review=False,
    )
    with pytest.raises(ValueError):
        DeliveryContractValidator().validate(request=Request(), decision=decision, channel='crm')


def test_validator_rejects_noncanonical_decision_path() -> None:
    decision = RoutingDecision(
        request_id='r1',
        selected_business_id='biz-1',
        runner_up_business_ids=(),
        trace={'decision_path': 'shadow_path', 'optimization_target': CANONICAL_OPTIMIZATION_TARGET},
        requires_manual_review=False,
    )
    with pytest.raises(ValueError):
        DeliveryContractValidator().validate(request=Request(), decision=decision, channel='crm')

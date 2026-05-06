from __future__ import annotations

from config.execution_contract import CANONICAL_DECISION_PATH, CANONICAL_OPTIMIZATION_TARGET
from contracts.matching.routing_decision import RoutingDecision
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher


class Request:
    request_id = 'r1'
    created_at_ms = 1


def test_lead_delivery_dispatcher() -> None:
    decision = RoutingDecision(
        'r1',
        'biz-1',
        (),
        {
            'decision_path': CANONICAL_DECISION_PATH,
            'delivery_channel': 'crm',
            'optimization_target': CANONICAL_OPTIMIZATION_TARGET,
        },
        False,
    )
    outcome = LeadDeliveryDispatcher().dispatch(request=Request(), decision=decision)
    assert outcome is not None
    assert outcome.channel == 'crm'

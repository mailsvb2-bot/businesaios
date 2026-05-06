from __future__ import annotations

import pytest

from contracts.matching.routing_decision import RoutingDecision
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher


class Request:
    request_id = 'r1'
    created_at_ms = 1


def test_delivery_requires_canonical_decision_trace() -> None:
    dispatcher = LeadDeliveryDispatcher()
    with pytest.raises(ValueError):
        dispatcher.dispatch(request=Request(), decision=RoutingDecision('r1', 'biz-1', (), {}, False))

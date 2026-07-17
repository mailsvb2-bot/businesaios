from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.ai import (
    _reset_decision_core_singleton_for_tests,
    set_decision_core_singleton,
)
from core.policies.demand_route_policy import DemandRoutePolicyV1
from demand_capture.demand_capture_service import DemandCaptureService
from demand_learning.closed_loop_optimizer import ClosedLoopOptimizer
from demand_os.demand_os_service import DemandOperatingSystemService
from intent.client_intent_builder import ClientIntentBuilder
from lead_outcomes import LeadOutcomeRegistry
from matching.match_engine import MatchEngine
from routing.demand_router import DemandRouter
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher
from supply_directory.business_directory import BusinessDirectory
from supply_state.business_live_state_builder import BusinessLiveStateBuilder


@pytest.fixture(autouse=True)
def _isolated_decision_core_singleton():
    _reset_decision_core_singleton_for_tests()
    try:
        yield
    finally:
        _reset_decision_core_singleton_for_tests()


class _PolicyEnvelopeCore:
    def issue(self, state):
        proposed = DemandRoutePolicyV1().propose(state)
        return SimpleNamespace(
            decision=SimpleNamespace(
                action=proposed.action,
                payload=proposed.payload,
                decision_id="signed-manual-review",
                correlation_id=str(state.session.get("request_id") or "request"),
            )
        )


class EmptyDirectory(BusinessDirectory):
    def list_profiles(self):
        return ()


def test_manual_review_request_rejects_conversion_outcome() -> None:
    directory = EmptyDirectory()
    state_builder = BusinessLiveStateBuilder()
    decision_core = _PolicyEnvelopeCore()
    set_decision_core_singleton(decision_core)
    service = DemandOperatingSystemService(
        demand_capture_service=DemandCaptureService(),
        client_intent_builder=ClientIntentBuilder(),
        business_live_state_builder=state_builder,
        business_directory=directory,
        match_engine=MatchEngine(),
        demand_router=DemandRouter(
            business_directory=directory,
            business_live_state_builder=state_builder,
        ),
        demand_decision_publisher=None,
        decision_core=decision_core,
        lead_delivery_dispatcher=LeadDeliveryDispatcher(),
        lead_outcome_registry=LeadOutcomeRegistry(),
        closed_loop_optimizer=ClosedLoopOptimizer(),
    )

    result = service.process_raw_request(
        {"text": "help", "channel": "website", "customer_id": "c1"}
    )

    assert result["decision"].requires_manual_review is True
    with pytest.raises(ValueError, match="manual review"):
        service.record_outcome(
            request_id=result["request"].request_id,
            converted=True,
            revenue=10.0,
        )

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from core.ai import set_decision_core_singleton
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


class CanonicalDemandPolicyIssuer:
    """Test issuer that delegates all route selection to the Canon policy."""

    def __init__(self) -> None:
        self.states: list[object] = []

    def issue(self, state):
        self.states.append(state)
        proposed = DemandRoutePolicyV1().propose(state)
        session = getattr(state, "session", None) or {}
        request_id = str(session.get("request_id") or "demand-request")
        return SimpleNamespace(
            decision=SimpleNamespace(
                action=proposed.action,
                payload=proposed.payload,
                decision_id=f"signed-demand-route:{request_id}",
                correlation_id=request_id,
            )
        )


def build_registered_demand_policy_issuer() -> CanonicalDemandPolicyIssuer:
    issuer = CanonicalDemandPolicyIssuer()
    set_decision_core_singleton(issuer)
    return issuer


def build_demand_os_service(
    *,
    directory: BusinessDirectory | None = None,
    dispatcher: Any | None = None,
    registry: LeadOutcomeRegistry | None = None,
    seed_defaults: bool = True,
) -> DemandOperatingSystemService:
    resolved_directory = directory or BusinessDirectory()
    if directory is None and seed_defaults:
        resolved_directory.seed_defaults()
    state_builder = BusinessLiveStateBuilder()
    return DemandOperatingSystemService(
        demand_capture_service=DemandCaptureService(),
        client_intent_builder=ClientIntentBuilder(),
        business_live_state_builder=state_builder,
        business_directory=resolved_directory,
        match_engine=MatchEngine(),
        demand_router=DemandRouter(
            business_directory=resolved_directory,
            business_live_state_builder=state_builder,
        ),
        demand_decision_publisher=None,
        decision_core=build_registered_demand_policy_issuer(),
        lead_delivery_dispatcher=(
            dispatcher or LeadDeliveryDispatcher()
        ),
        lead_outcome_registry=registry or LeadOutcomeRegistry(),
        closed_loop_optimizer=ClosedLoopOptimizer(),
    )


__all__ = [
    "CanonicalDemandPolicyIssuer",
    "build_demand_os_service",
    "build_registered_demand_policy_issuer",
]

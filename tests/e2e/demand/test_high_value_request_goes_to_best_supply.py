from __future__ import annotations

from core.application.decision_service import DecisionService
from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.scorers.selector import DecisionSelector
from core.policy.decision_validator import DecisionValidator
from demand_capture.demand_capture_service import DemandCaptureService
from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge
from intent.client_intent_builder import ClientIntentBuilder
from matching.match_engine import MatchEngine
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus
from routing.demand_router import DemandRouter
from supply_directory.business_directory import BusinessDirectory
from supply_state.business_live_state_builder import BusinessLiveStateBuilder


def test_high_value_request_goes_to_best_supply():
    request = DemandCaptureService().capture({"text": "premium vip urgent", "channel": "website", "customer_id": "c1"})
    intent = ClientIntentBuilder().build(request)
    directory = BusinessDirectory(); directory.seed_defaults()
    state_builder = BusinessLiveStateBuilder()
    bundle = MatchEngine().build_bundle(request=request, intent=intent, profiles=directory.list_profiles(), live_states=tuple(state_builder.build(p.business_id) for p in directory.list_profiles()))
    prepared = DemandRouter(business_directory=directory, business_live_state_builder=state_builder).prepare(request=request, intent=intent, match_bundle=bundle)
    bridge = CanonicalDemandDecisionBridge(decision_core=DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), EventBus()), DecisionHistory()))
    decision = bridge.issue(request=request, routing_preparation=prepared)
    assert decision.selected_business_id in {"biz-1", "biz-2", "biz-3"}

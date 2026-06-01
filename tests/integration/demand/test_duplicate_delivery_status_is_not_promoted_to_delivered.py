from __future__ import annotations

from contracts.matching.delivery_outcome import DeliveryOutcome
from core.application.decision_service import DecisionService
from core.policy.decision_history import DecisionHistory
from core.policy.decision_publisher import DecisionPublisher
from core.policy.decision_validator import DecisionValidator
from core.scorers.selector import DecisionSelector
from demand_capture.demand_capture_service import DemandCaptureService
from demand_learning.closed_loop_optimizer import ClosedLoopOptimizer
from demand_os.demand_os_service import DemandOperatingSystemService
from intent.client_intent_builder import ClientIntentBuilder
from lead_outcomes import LeadOutcomeRegistry
from matching.match_engine import MatchEngine
from observability.decision_audit_log import DecisionAuditLog
from observability.event_bus import EventBus
from routing.demand_router import DemandRouter
from supply_directory.business_directory import BusinessDirectory
from supply_state.business_live_state_builder import BusinessLiveStateBuilder


class DuplicateDispatcher:
    def dispatch(self, *, request, decision):
        return DeliveryOutcome(
            request_id=request.request_id,
            business_id=decision.selected_business_id or 'biz-1',
            delivery_status='duplicate',
            channel='crm',
            detail='duplicate',
            delivered_at_ms=None,
        )


def _make_service(registry: LeadOutcomeRegistry) -> DemandOperatingSystemService:
    directory = BusinessDirectory()
    directory.seed_defaults()
    state_builder = BusinessLiveStateBuilder()
    return DemandOperatingSystemService(
        demand_capture_service=DemandCaptureService(),
        client_intent_builder=ClientIntentBuilder(),
        business_live_state_builder=state_builder,
        business_directory=directory,
        match_engine=MatchEngine(),
        demand_router=DemandRouter(business_directory=directory, business_live_state_builder=state_builder),
        demand_decision_publisher=None,
        decision_core=DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), EventBus()), DecisionHistory()),
        lead_delivery_dispatcher=DuplicateDispatcher(),
        lead_outcome_registry=registry,
        closed_loop_optimizer=ClosedLoopOptimizer(),
    )


def test_duplicate_delivery_status_is_preserved() -> None:
    registry = LeadOutcomeRegistry()
    service = _make_service(registry)
    result = service.process_raw_request({'request_id': 'r-dup', 'text': 'premium service amsterdam', 'channel': 'website', 'customer_id': 'c1'})
    assert result['delivery'] is not None
    assert result['delivery'].delivery_status == 'duplicate'
    assert registry.require('r-dup')['status'] == 'duplicate'

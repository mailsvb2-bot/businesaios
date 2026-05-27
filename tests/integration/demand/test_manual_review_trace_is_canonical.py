from __future__ import annotations

from contracts.supply import BusinessSupplyProfile
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
from routing_execution.lead_delivery_dispatcher import LeadDeliveryDispatcher
from supply_directory.business_directory import BusinessDirectory
from supply_state.business_live_state_builder import BusinessLiveStateBuilder


def test_manual_review_trace_is_canonical_when_all_supply_blocked() -> None:
    directory = BusinessDirectory()
    directory.add_profile(BusinessSupplyProfile(
        business_id='biz-blocked',
        name='Blocked',
        service_categories=('general',),
        service_area_codes=('amsterdam',),
        price_band='mid',
        notification_channels=('email',),
        tags=(),
        active=False,
    ))
    state_builder = BusinessLiveStateBuilder()
    service = DemandOperatingSystemService(
        demand_capture_service=DemandCaptureService(),
        client_intent_builder=ClientIntentBuilder(),
        business_live_state_builder=state_builder,
        business_directory=directory,
        match_engine=MatchEngine(),
        demand_router=DemandRouter(business_directory=directory, business_live_state_builder=state_builder),
        demand_decision_publisher=None,
        decision_core=DecisionService(DecisionSelector(), DecisionValidator(), DecisionPublisher(DecisionAuditLog(), EventBus()), DecisionHistory()),
        lead_delivery_dispatcher=LeadDeliveryDispatcher(),
        lead_outcome_registry=LeadOutcomeRegistry(),
        closed_loop_optimizer=ClosedLoopOptimizer(),
    )
    result = service.process_raw_request({'text': 'service amsterdam', 'channel': 'website', 'customer_id': 'c1'})
    assert result['decision'].requires_manual_review is True
    assert result['decision'].trace['decision_path'] == 'core.decision'

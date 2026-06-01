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


def test_outcome_timestamp_is_monotonic_and_not_before_delivery() -> None:
    directory = BusinessDirectory()
    directory.seed_defaults()
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
    result = service.process_raw_request({
        'customer_id': 'cust-1',
        'text': 'need therapist',
        'channel': 'telegram',
        'created_at_ms': 1000,
    })
    request_id = result['request'].request_id
    seeded = service._outcomes.require(request_id)
    assert int(seeded['outcome_updated_at_ms']) >= int(seeded['created_at_ms'])
    service.record_outcome(request_id=request_id, converted=True, revenue=50.0)
    updated = service._outcomes.require(request_id)
    assert int(updated['outcome_updated_at_ms']) > int(seeded['outcome_updated_at_ms'])

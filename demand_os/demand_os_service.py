from __future__ import annotations

from demand_decision.canonical_decision_bridge import CanonicalDemandDecisionBridge
from demand_gravity.demand_gravity_model import DemandGravityModel
from demand_learning.closed_loop_optimizer import ClosedLoopOptimizer
from demand_os.demand_os_readiness import REQUIRED_COMPONENTS, evaluate_readiness
from demand_os.demand_os_snapshot import DemandOsSnapshot
from demand_os.outcome_recorder import DemandOutcomeRecorder
from demand_os.request_pipeline import DemandRequestPipeline
from lead_outcomes import LeadOutcomeRegistry
from runtime.service_names import RuntimeServiceName


class DemandOperatingSystemService:
    def __init__(
        self,
        *,
        demand_capture_service: object,
        client_intent_builder: object,
        business_live_state_builder: object,
        business_directory: object,
        match_engine: object,
        demand_router: object,
        demand_decision_publisher: object | None,
        decision_core: object | None = None,
        lead_delivery_dispatcher: object,
        demand_gravity_model: object | None = None,
        lead_outcome_registry: LeadOutcomeRegistry | None = None,
        closed_loop_optimizer: ClosedLoopOptimizer | None = None,
        event_log: object | None = None,
    ) -> None:
        if demand_decision_publisher is not None:
            raise ValueError('retired demand_decision_publisher cannot be wired into DemandOperatingSystemService')
        self._snapshot = DemandOsSnapshot()
        self._optimizer = closed_loop_optimizer or ClosedLoopOptimizer()
        self._outcomes = lead_outcome_registry or LeadOutcomeRegistry()
        readiness = evaluate_readiness({
            'demand_capture_service': demand_capture_service,
            'client_intent_builder': client_intent_builder,
            'business_live_state_builder': business_live_state_builder,
            'business_directory': business_directory,
            'match_engine': match_engine,
            'demand_router': demand_router,
            RuntimeServiceName.DECISION_CORE: decision_core,
            'lead_delivery_dispatcher': lead_delivery_dispatcher,
        })
        if not readiness.ready:
            raise ValueError(f'demand os not ready: {readiness.detail}')
        if decision_core is None:
            raise RuntimeError('DecisionCore is required for final demand decisions')
        decision_bridge = CanonicalDemandDecisionBridge(decision_core=decision_core)
        self._pipeline = DemandRequestPipeline(
            capture=demand_capture_service,
            intent_builder=client_intent_builder,
            business_directory=business_directory,
            state_builder=business_live_state_builder,
            gravity_model=demand_gravity_model or DemandGravityModel(),
            match_engine=match_engine,
            router=demand_router,
            decision_bridge=decision_bridge,
            delivery_dispatcher=lead_delivery_dispatcher,
            snapshot=self._snapshot,
            event_log=event_log,
        )
        self._outcome_recorder = DemandOutcomeRecorder(
            outcomes=self._outcomes,
            optimizer=self._optimizer,
            event_log=event_log,
        )

    def process_raw_request(self, raw_event: dict[str, object]) -> dict[str, object]:
        bundle = self._pipeline.process(raw_event=raw_event, optimizer=self._optimizer)
        self._outcome_recorder.seed(request=bundle.request, decision=bundle.decision, delivery=bundle.delivery)
        result = bundle.as_dict()
        result['required_components'] = REQUIRED_COMPONENTS
        return result

    def record_outcome(self, *, request_id: str, converted: bool, revenue: float = 0.0, quality_issue: bool = False, refunded: bool = False, lost: bool = False) -> dict[str, object]:
        return self._outcome_recorder.record(
            request_id=request_id,
            converted=converted,
            revenue=revenue,
            quality_issue=quality_issue,
            refunded=refunded,
            lost=lost,
        )

    def snapshot(self) -> DemandOsSnapshot:
        return self._snapshot

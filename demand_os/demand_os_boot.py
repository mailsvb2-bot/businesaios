from __future__ import annotations

from runtime.service_names import RuntimeServiceName

from demand_os.demand_os_registry import DemandOsRegistry
from demand_os.demand_os_readiness import evaluate_readiness
from demand_os.demand_os_service import DemandOperatingSystemService


def boot_demand_os(registry: DemandOsRegistry) -> DemandOperatingSystemService:
    components = registry.snapshot()
    readiness = evaluate_readiness(components)
    if not readiness.ready:
        raise RuntimeError(readiness.reason)
    return DemandOperatingSystemService(
        demand_capture_service=registry.require('demand_capture_service'),
        client_intent_builder=registry.require('client_intent_builder'),
        business_live_state_builder=registry.require('business_live_state_builder'),
        business_directory=registry.require('business_directory'),
        match_engine=registry.require('match_engine'),
        demand_router=registry.require('demand_router'),
        demand_decision_publisher=None,
        decision_core=registry.require(RuntimeServiceName.DECISION_CORE),
        lead_delivery_dispatcher=registry.require('lead_delivery_dispatcher'),
        demand_gravity_model=components.get('demand_gravity_model'),
        lead_outcome_registry=components.get('lead_outcome_registry'),
        closed_loop_optimizer=components.get('closed_loop_optimizer'),
        event_log=components.get('event_log'),
    )

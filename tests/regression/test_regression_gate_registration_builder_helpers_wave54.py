from __future__ import annotations

from boot.registrations.register_architecture_watch import register_architecture_watch
from boot.registrations.register_autonomy_advisor import register_autonomy_advisor
from boot.registrations.register_creative_intelligence import register_creative_intelligence
from boot.registrations.register_diffusion_watch import register_diffusion_watch
from boot.registrations.register_flow_watch import register_flow_watch
from boot.registrations.register_market_watch import register_market_watch
from boot.registrations.register_observability import register_observability
from boot.registrations.register_runtime_packet_provider import register_runtime_packet_provider
from boot.registrations.register_runtime_state_enrichment import register_runtime_state_enrichment
from boot.registrations.register_structure_watch import register_structure_watch
from boot.registrations.register_world_state_integration import register_world_state_integration
from runtime.registry import RuntimeRegistry
from runtime.service_names import RuntimeServiceName


def test_registration_builder_helpers_preserve_runtime_contracts() -> None:
    registry = RuntimeRegistry()
    registry.begin_registration()

    observability_result = register_observability(registry)
    market_watch_result = register_market_watch(registry)
    architecture_watch_result = register_architecture_watch(registry)
    structure_watch_result = register_structure_watch(registry)
    flow_watch_result = register_flow_watch(registry)
    diffusion_watch_result = register_diffusion_watch(registry)
    creative_intelligence_result = register_creative_intelligence(registry)
    autonomy_advisor_result = register_autonomy_advisor(registry)
    world_state_result = register_world_state_integration(registry)
    packet_provider_result = register_runtime_packet_provider(registry)
    state_enrichment_result = register_runtime_state_enrichment(registry)

    assert observability_result.service_name is RuntimeServiceName.OBSERVABILITY
    assert market_watch_result.service_name is RuntimeServiceName.MARKET_WATCH
    assert architecture_watch_result.service_name is RuntimeServiceName.ARCHITECTURE_WATCH
    assert structure_watch_result.service_name is RuntimeServiceName.STRUCTURE_WATCH
    assert flow_watch_result.service_name is RuntimeServiceName.FLOW_WATCH
    assert diffusion_watch_result.service_name is RuntimeServiceName.DIFFUSION_WATCH
    assert creative_intelligence_result.service_name is RuntimeServiceName.CREATIVE_INTELLIGENCE
    assert autonomy_advisor_result.service_name is RuntimeServiceName.AUTONOMY_ADVISOR
    assert world_state_result.service_name is RuntimeServiceName.WORLD_STATE_INTEGRATION
    assert packet_provider_result.service_name is RuntimeServiceName.RUNTIME_PACKET_PROVIDER
    assert state_enrichment_result.service_name is RuntimeServiceName.RUNTIME_STATE_ENRICHMENT

    for service_name in (
        RuntimeServiceName.OBSERVABILITY,
        RuntimeServiceName.MARKET_WATCH,
        RuntimeServiceName.ARCHITECTURE_WATCH,
        RuntimeServiceName.STRUCTURE_WATCH,
        RuntimeServiceName.FLOW_WATCH,
        RuntimeServiceName.DIFFUSION_WATCH,
        RuntimeServiceName.CREATIVE_INTELLIGENCE,
        RuntimeServiceName.AUTONOMY_ADVISOR,
        RuntimeServiceName.WORLD_STATE_INTEGRATION,
        RuntimeServiceName.RUNTIME_PACKET_PROVIDER,
        RuntimeServiceName.RUNTIME_STATE_ENRICHMENT,
    ):
        assert registry.get(service_name) is not None

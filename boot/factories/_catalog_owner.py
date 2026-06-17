from __future__ import annotations

from typing import Callable, Final

from boot.runtime_service_specs import CATALOG_BACKED_FACTORY_NAMES
from runtime.errors import RuntimeConfigurationError
from runtime.runtime_observability import RuntimeObservability
from runtime.service_names import RuntimeServiceName
from runtime.integration.runtime_packet_provider import RuntimePacketProvider
from runtime.decision_input.decision_input_service import DecisionInputService, build_decision_input_service as build_runtime_decision_input_service
from runtime.decision_gateway import (
    RuntimeDecisionRouteGateway,
    build_runtime_decision_gateway,
)
from runtime.decision_input.runtime_state_enrichment import RuntimeStateEnrichmentService, build_runtime_state_enrichment_service as build_runtime_state_enrichment_service_owner
from runtime.architecture.architecture_watch_service import ArchitectureWatchService
from runtime.advisory.autonomy_advisor_service import AutonomyAdvisorService
from runtime.creative.creative_intelligence_service import CreativeIntelligenceService
from runtime.diffusion.diffusion_watch_service import DiffusionWatchService
from runtime.flow.flow_watch_service import FlowWatchService
from runtime.market.market_watch_service import MarketWatchService
from runtime.market.market_trend_engine import MarketTrendEngine
from runtime.structure.structure_watch_service import StructureWatchService
from runtime.integration.world_state_integration_service import WorldStateIntegrationService
from boot.factories.decision_core_factory import build_runtime_decision_execution_service

COMPAT_FACTORY_EXPORTS: Final[dict[str, str]] = {
    'build_architecture_watch_service': 'architecture_watch_factory',
    'build_autonomy_advisor_service': 'autonomy_advisor_factory',
    'build_creative_intelligence_service': 'creative_intelligence_factory',
    'build_decision_gateway': 'decision_gateway_factory',
    'build_runtime_decision_execution_service': 'decision_core_factory',
    'build_decision_input_service': 'decision_input_service_factory',
    'build_diffusion_watch_service': 'diffusion_watch_factory',
    'build_flow_watch_service': 'flow_watch_factory',
    'build_market_watch_service': 'market_watch_factory',
    'build_runtime_packet_provider': 'runtime_packet_provider_factory',
    'build_runtime_state_enrichment_service': 'runtime_state_enrichment_factory',
    'build_structure_watch_service': 'structure_watch_factory',
    'build_world_state_integration_service': 'world_state_integration_factory',
}


def build_architecture_watch_service(*, observability: RuntimeObservability) -> ArchitectureWatchService:
    return ArchitectureWatchService(observability=observability)


def build_autonomy_advisor_service(*, observability: RuntimeObservability) -> AutonomyAdvisorService:
    return AutonomyAdvisorService(observability=observability)


def build_creative_intelligence_service(*, observability: RuntimeObservability) -> CreativeIntelligenceService:
    return CreativeIntelligenceService(observability=observability)



def build_decision_gateway(
    *,
    decision_input_service: DecisionInputService,
    enrichment_service: RuntimeStateEnrichmentService,
    observability: RuntimeObservability,
) -> RuntimeDecisionRouteGateway:
    return build_runtime_decision_gateway(
        decision_input_service=decision_input_service,
        enrichment_service=enrichment_service,
        observability=observability,
    )


def build_decision_input_service(*, observability: RuntimeObservability) -> DecisionInputService:
    return build_runtime_decision_input_service(observability=observability)


def build_diffusion_watch_service(*, observability: RuntimeObservability) -> DiffusionWatchService:
    return DiffusionWatchService(observability=observability)


def build_flow_watch_service(*, observability: RuntimeObservability) -> FlowWatchService:
    return FlowWatchService(observability=observability)


def build_market_watch_service(*, observability: RuntimeObservability) -> MarketWatchService:
    return MarketWatchService(trend_engine=MarketTrendEngine(), observability=observability)


def build_runtime_packet_provider(
    *,
    integration_service: WorldStateIntegrationService,
    observability: RuntimeObservability,
) -> RuntimePacketProvider:
    return RuntimePacketProvider(
        integration_service=integration_service,
        observability=observability,
    )


def build_runtime_state_enrichment_service(*, observability: RuntimeObservability) -> RuntimeStateEnrichmentService:
    return build_runtime_state_enrichment_service_owner(observability=observability)


def build_structure_watch_service(*, observability: RuntimeObservability) -> StructureWatchService:
    return StructureWatchService(observability=observability)


def build_world_state_integration_service(*, observability: RuntimeObservability) -> WorldStateIntegrationService:
    return WorldStateIntegrationService(observability=observability)


LOCAL_FACTORY_FUNCTION_NAMES: Final[tuple[str, ...]] = (
    'build_architecture_watch_service',
    'build_autonomy_advisor_service',
    'build_creative_intelligence_service',
    'build_decision_gateway',
    'build_decision_input_service',
    'build_diffusion_watch_service',
    'build_flow_watch_service',
    'build_market_watch_service',
    'build_runtime_packet_provider',
    'build_runtime_state_enrichment_service',
    'build_structure_watch_service',
    'build_world_state_integration_service',
)

FACTORY_FUNCTIONS: Final[dict[str, Callable[..., object]]] = {
    name: globals()[name]
    for name in LOCAL_FACTORY_FUNCTION_NAMES
}
FACTORY_SERVICE_NAMES: Final[dict[str, str]] = dict(CATALOG_BACKED_FACTORY_NAMES)


def get_factory_for_service(service_name: str) -> Callable[..., object]:
    try:
        factory_name = FACTORY_SERVICE_NAMES[str(service_name)]
        return FACTORY_FUNCTIONS[factory_name]
    except KeyError as exc:
        raise RuntimeConfigurationError(f'Factory catalog drift: no factory for runtime service {service_name!r}') from exc


_missing_factories = sorted(
    factory_name
    for factory_name in FACTORY_SERVICE_NAMES.values()
    if factory_name not in FACTORY_FUNCTIONS
)
if _missing_factories:
    raise RuntimeConfigurationError(
        'Factory catalog drift: missing implementations for ' + ', '.join(_missing_factories)
    )

_unmapped_factories = sorted(
    factory_name
    for factory_name in FACTORY_FUNCTIONS
    if factory_name not in set(FACTORY_SERVICE_NAMES.values())
)
if _unmapped_factories:
    raise RuntimeConfigurationError(
        'Factory catalog drift: local factories are not mapped to runtime services: '
        + ', '.join(_unmapped_factories)
    )

__all__ = [
    'COMPAT_FACTORY_EXPORTS',
    'FACTORY_FUNCTIONS',
    'FACTORY_SERVICE_NAMES',
    'get_factory_for_service',
    'build_architecture_watch_service',
    'build_autonomy_advisor_service',
    'build_creative_intelligence_service',
    'build_decision_gateway',
    'build_runtime_decision_execution_service',
    'build_decision_input_service',
    'build_diffusion_watch_service',
    'build_flow_watch_service',
    'build_market_watch_service',
    'build_runtime_packet_provider',
    'build_runtime_state_enrichment_service',
    'build_structure_watch_service',
    'build_world_state_integration_service',
]

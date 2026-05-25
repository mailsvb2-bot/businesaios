from __future__ import annotations

"""Canonical runtime service spec catalog.

The catalog maps runtime service names to registration/factory callables. It is
metadata only: it must not instantiate services or create a second runtime path.
"""

from dataclasses import dataclass, field
from typing import Final

from boot.runtime_dependency_sets import RUNTIME_DEPENDENCY_SETS
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType

CANON_RUNTIME_SERVICE_SPEC_CATALOG_OWNER: Final[bool] = True


@dataclass(frozen=True)
class RuntimeServiceSpec:
    service_name: str
    service_type: str
    registration_callable: str
    factory_callable: str | None = None
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    dependency_map: dict[str, str] = field(default_factory=dict)


def _spec(
    service_name: str,
    service_type: str,
    registration_callable: str,
    factory_callable: str | None = None,
    dependency_map: dict[str, str] | None = None,
) -> RuntimeServiceSpec:
    return RuntimeServiceSpec(
        service_name=service_name,
        service_type=service_type,
        registration_callable=registration_callable,
        factory_callable=factory_callable,
        dependencies=RUNTIME_DEPENDENCY_SETS.get(service_name, ()),
        dependency_map=dict(dependency_map or {}),
    )

CATALOG_BACKED_RUNTIME_SPECS: Final[tuple[RuntimeServiceSpec, ...]] = (
    _spec(RuntimeServiceName.ARCHITECTURE_WATCH, RuntimeServiceType.GUARD, "register_architecture_watch", "build_architecture_watch_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.AUTONOMY_ADVISOR, RuntimeServiceType.GUARD, "register_autonomy_advisor", "build_autonomy_advisor_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.CREATIVE_INTELLIGENCE, RuntimeServiceType.CORE, "register_creative_intelligence", "build_creative_intelligence_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.DECISION_GATEWAY, RuntimeServiceType.CORE, "register_decision_gateway", "build_decision_gateway", {"decision_input_service": RuntimeServiceName.DECISION_INPUT_SERVICE, "enrichment_service": RuntimeServiceName.RUNTIME_STATE_ENRICHMENT, "observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.DECISION_INPUT_SERVICE, RuntimeServiceType.CORE, "register_decision_input_service", "build_decision_input_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.DIFFUSION_WATCH, RuntimeServiceType.GUARD, "register_diffusion_watch", "build_diffusion_watch_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.FLOW_WATCH, RuntimeServiceType.GUARD, "register_flow_watch", "build_flow_watch_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.MARKET_WATCH, RuntimeServiceType.GUARD, "register_market_watch", "build_market_watch_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.RUNTIME_PACKET_PROVIDER, RuntimeServiceType.CORE, "register_runtime_packet_provider", "build_runtime_packet_provider", {"integration_service": RuntimeServiceName.WORLD_STATE_INTEGRATION, "observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.RUNTIME_STATE_ENRICHMENT, RuntimeServiceType.CORE, "register_runtime_state_enrichment", "build_runtime_state_enrichment_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.STRUCTURE_WATCH, RuntimeServiceType.GUARD, "register_structure_watch", "build_structure_watch_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
    _spec(RuntimeServiceName.WORLD_STATE_INTEGRATION, RuntimeServiceType.CORE, "register_world_state_integration", "build_world_state_integration_service", {"observability": RuntimeServiceName.OBSERVABILITY}),
)

SINGLETON_RUNTIME_SPECS: Final[tuple[RuntimeServiceSpec, ...]] = (
    _spec(RuntimeServiceName.OBSERVABILITY, RuntimeServiceType.GUARD, "register_observability"),
    _spec(RuntimeServiceName.RISK_ENGINE, RuntimeServiceType.GUARD, "register_risk"),
    _spec(RuntimeServiceName.REWARD_GUARD, RuntimeServiceType.GUARD, "register_reward"),
    _spec(RuntimeServiceName.SIMULATION_GATE, RuntimeServiceType.GUARD, "register_simulation"),
    _spec(RuntimeServiceName.KILL_SWITCH, RuntimeServiceType.GUARD, "register_kill_switch"),
    _spec(RuntimeServiceName.ACTION_BUDGET, RuntimeServiceType.GUARD, "register_action_budget"),
)

EXPLICIT_RUNTIME_SPECS: Final[tuple[RuntimeServiceSpec, ...]] = (
    _spec(RuntimeServiceName.GOVERNANCE_CHAIN, RuntimeServiceType.GOVERNANCE, "register_governance"),
    _spec(RuntimeServiceName.ACTION_EXECUTOR, RuntimeServiceType.EXECUTOR, "register_action_executor"),
    _spec(RuntimeServiceName.DECISION_CORE, RuntimeServiceType.CORE, "register_decision_core"),
)

RUNTIME_SERVICE_SPECS: Final[tuple[RuntimeServiceSpec, ...]] = (
    *SINGLETON_RUNTIME_SPECS,
    *EXPLICIT_RUNTIME_SPECS,
    *CATALOG_BACKED_RUNTIME_SPECS,
)

RUNTIME_SERVICE_SPEC_BY_NAME: Final[dict[str, RuntimeServiceSpec]] = {spec.service_name: spec for spec in RUNTIME_SERVICE_SPECS}
RUNTIME_SERVICE_SPEC_BY_CALLABLE: Final[dict[str, RuntimeServiceSpec]] = {spec.registration_callable: spec for spec in RUNTIME_SERVICE_SPECS}

SINGLETON_RUNTIME_CALLABLES: Final[tuple[str, ...]] = tuple(spec.registration_callable for spec in SINGLETON_RUNTIME_SPECS)
CATALOG_BACKED_RUNTIME_CALLABLES: Final[tuple[str, ...]] = tuple(spec.registration_callable for spec in CATALOG_BACKED_RUNTIME_SPECS)
CATALOG_BACKED_RUNTIME_SERVICES: Final[tuple[str, ...]] = tuple(spec.service_name for spec in CATALOG_BACKED_RUNTIME_SPECS)
CATALOG_BACKED_FACTORY_NAMES: Final[dict[str, str]] = {
    spec.service_name: str(spec.factory_callable)
    for spec in CATALOG_BACKED_RUNTIME_SPECS
    if spec.factory_callable
}


def get_runtime_service_spec(service_name: str) -> RuntimeServiceSpec:
    return RUNTIME_SERVICE_SPEC_BY_NAME[service_name]


def get_runtime_service_spec_by_callable(callable_name: str) -> RuntimeServiceSpec:
    return RUNTIME_SERVICE_SPEC_BY_CALLABLE[callable_name]


def build_registration_compat_exports(*, callable_names: tuple[str, ...]) -> dict[str, str]:
    return {name: name for name in callable_names}


__all__ = [
    "CANON_RUNTIME_SERVICE_SPEC_CATALOG_OWNER",
    "CATALOG_BACKED_FACTORY_NAMES",
    "CATALOG_BACKED_RUNTIME_CALLABLES",
    "CATALOG_BACKED_RUNTIME_SERVICES",
    "CATALOG_BACKED_RUNTIME_SPECS",
    "EXPLICIT_RUNTIME_SPECS",
    "RUNTIME_SERVICE_SPECS",
    "RUNTIME_SERVICE_SPEC_BY_CALLABLE",
    "RUNTIME_SERVICE_SPEC_BY_NAME",
    "RuntimeServiceSpec",
    "SINGLETON_RUNTIME_CALLABLES",
    "SINGLETON_RUNTIME_SPECS",
    "build_registration_compat_exports",
    "get_runtime_service_spec",
    "get_runtime_service_spec_by_callable",
]

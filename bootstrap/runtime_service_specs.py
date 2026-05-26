from __future__ import annotations

"""Final owner for runtime service specs.

Physical ownership moved from `boot/*` to `bootstrap/*`.
Legacy boot surfaces remain thin compatibility shells."""

CANON_RUNTIME_SERVICE_SPECS_FINAL_OWNER = True
CANON_RUNTIME_SERVICE_SPECS_SINGLE_SOURCE = True


"""Canonical runtime service specifications for boot wiring.

This module is the single source of truth for runtime boot ordering,
dependency declarations, and catalog-backed dependency maps. It exists to
shrink duplication across:
- boot.runtime_dependency_sets
- boot.runtime_boot_manifest
- boot.registrations

It does not create a second execution path: the runtime boot manifest still
remains the only boot contract consumed by the orchestrator.
"""

from dataclasses import dataclass, field
from typing import Final

from runtime.manifest_entry import RuntimeManifestEntry
from runtime.service_names import RuntimeServiceName
from runtime.service_types import RuntimeServiceType


@dataclass(frozen=True)
class RuntimeServiceSpec:
    step_name: str
    callable_name: str
    service_name: str
    service_type: str
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    dependency_map: dict[str, str] = field(default_factory=dict)
    builder_name: str | None = None

    def __post_init__(self) -> None:
        builder_name = self.builder_name
        if builder_name is None and (self.dependency_map or self.service_name in _CATALOG_ALWAYS_BUILT_SERVICES):
            builder_name = _DEFAULT_BUILDER_NAMES_BY_SERVICE.get(self.service_name)
        object.__setattr__(self, "builder_name", builder_name)

    @property
    def module_path(self) -> str:
        return f"boot.registrations.{self.callable_name}"

    def as_manifest_entry(self) -> RuntimeManifestEntry:
        return RuntimeManifestEntry(
            step_name=self.step_name,
            module_path=self.module_path,
            callable_name=self.callable_name,
            service_name=self.service_name,
            service_type=self.service_type,
            dependencies=tuple(self.dependencies),
        )


_CATALOG_ALWAYS_BUILT_SERVICES: Final[frozenset[str]] = frozenset({
    RuntimeServiceName.ARCHITECTURE_WATCH,
    RuntimeServiceName.STRUCTURE_WATCH,
    RuntimeServiceName.FLOW_WATCH,
    RuntimeServiceName.DIFFUSION_WATCH,
    RuntimeServiceName.MARKET_WATCH,
})

_DEFAULT_BUILDER_NAMES_BY_SERVICE: Final[dict[str, str]] = {
    RuntimeServiceName.ARCHITECTURE_WATCH: "build_architecture_watch_service",
    RuntimeServiceName.AUTONOMY_ADVISOR: "build_autonomy_advisor_service",
    RuntimeServiceName.CREATIVE_INTELLIGENCE: "build_creative_intelligence_service",
    RuntimeServiceName.DECISION_GATEWAY: "build_decision_gateway",
    RuntimeServiceName.DECISION_INPUT_SERVICE: "build_decision_input_service",
    RuntimeServiceName.DIFFUSION_WATCH: "build_diffusion_watch_service",
    RuntimeServiceName.FLOW_WATCH: "build_flow_watch_service",
    RuntimeServiceName.MARKET_WATCH: "build_market_watch_service",
    RuntimeServiceName.RUNTIME_PACKET_PROVIDER: "build_runtime_packet_provider",
    RuntimeServiceName.RUNTIME_STATE_ENRICHMENT: "build_runtime_state_enrichment_service",
    RuntimeServiceName.STRUCTURE_WATCH: "build_structure_watch_service",
    RuntimeServiceName.WORLD_STATE_INTEGRATION: "build_world_state_integration_service",
}


_RUNTIME_SPECS: Final[tuple[RuntimeServiceSpec, ...]] = (
    RuntimeServiceSpec(
        step_name="register_observability",
        callable_name="register_observability",
        service_name=RuntimeServiceName.OBSERVABILITY,
        service_type=RuntimeServiceType.GUARD,
    ),
    RuntimeServiceSpec(
        step_name="register_architecture_watch",
        callable_name="register_architecture_watch",
        service_name=RuntimeServiceName.ARCHITECTURE_WATCH,
        service_type=RuntimeServiceType.GUARD,
        dependencies=(RuntimeServiceName.OBSERVABILITY,),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_structure_watch",
        callable_name="register_structure_watch",
        service_name=RuntimeServiceName.STRUCTURE_WATCH,
        service_type=RuntimeServiceType.GUARD,
        dependencies=(RuntimeServiceName.OBSERVABILITY,),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_flow_watch",
        callable_name="register_flow_watch",
        service_name=RuntimeServiceName.FLOW_WATCH,
        service_type=RuntimeServiceType.GUARD,
        dependencies=(RuntimeServiceName.OBSERVABILITY,),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_diffusion_watch",
        callable_name="register_diffusion_watch",
        service_name=RuntimeServiceName.DIFFUSION_WATCH,
        service_type=RuntimeServiceType.GUARD,
        dependencies=(RuntimeServiceName.OBSERVABILITY,),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_market_watch",
        callable_name="register_market_watch",
        service_name=RuntimeServiceName.MARKET_WATCH,
        service_type=RuntimeServiceType.GUARD,
        dependencies=(RuntimeServiceName.OBSERVABILITY,),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_creative_intelligence",
        callable_name="register_creative_intelligence",
        service_name=RuntimeServiceName.CREATIVE_INTELLIGENCE,
        service_type=RuntimeServiceType.GUARD,
        dependencies=(
            RuntimeServiceName.OBSERVABILITY,
            RuntimeServiceName.MARKET_WATCH,
        ),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_autonomy_advisor",
        callable_name="register_autonomy_advisor",
        service_name=RuntimeServiceName.AUTONOMY_ADVISOR,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=(
            RuntimeServiceName.OBSERVABILITY,
            RuntimeServiceName.CREATIVE_INTELLIGENCE,
            RuntimeServiceName.MARKET_WATCH,
            RuntimeServiceName.ARCHITECTURE_WATCH,
            RuntimeServiceName.STRUCTURE_WATCH,
            RuntimeServiceName.FLOW_WATCH,
            RuntimeServiceName.DIFFUSION_WATCH,
        ),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_world_state_integration",
        callable_name="register_world_state_integration",
        service_name=RuntimeServiceName.WORLD_STATE_INTEGRATION,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=(
            RuntimeServiceName.OBSERVABILITY,
            RuntimeServiceName.AUTONOMY_ADVISOR,
            RuntimeServiceName.CREATIVE_INTELLIGENCE,
            RuntimeServiceName.MARKET_WATCH,
            RuntimeServiceName.ARCHITECTURE_WATCH,
            RuntimeServiceName.STRUCTURE_WATCH,
            RuntimeServiceName.FLOW_WATCH,
            RuntimeServiceName.DIFFUSION_WATCH,
        ),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_decision_input_service",
        callable_name="register_decision_input_service",
        service_name=RuntimeServiceName.DECISION_INPUT_SERVICE,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=(
            RuntimeServiceName.OBSERVABILITY,
            RuntimeServiceName.WORLD_STATE_INTEGRATION,
        ),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_runtime_packet_provider",
        callable_name="register_runtime_packet_provider",
        service_name=RuntimeServiceName.RUNTIME_PACKET_PROVIDER,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=(
            RuntimeServiceName.WORLD_STATE_INTEGRATION,
            RuntimeServiceName.OBSERVABILITY,
        ),
        dependency_map={
            "integration_service": RuntimeServiceName.WORLD_STATE_INTEGRATION,
            "observability": RuntimeServiceName.OBSERVABILITY,
        },
    ),
    RuntimeServiceSpec(
        step_name="register_runtime_state_enrichment",
        callable_name="register_runtime_state_enrichment",
        service_name=RuntimeServiceName.RUNTIME_STATE_ENRICHMENT,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=(RuntimeServiceName.OBSERVABILITY,),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        step_name="register_decision_gateway",
        callable_name="register_decision_gateway",
        service_name=RuntimeServiceName.DECISION_GATEWAY,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=(
            RuntimeServiceName.DECISION_INPUT_SERVICE,
            RuntimeServiceName.RUNTIME_STATE_ENRICHMENT,
            RuntimeServiceName.OBSERVABILITY,
        ),
        dependency_map={
            "decision_input_service": RuntimeServiceName.DECISION_INPUT_SERVICE,
            "enrichment_service": RuntimeServiceName.RUNTIME_STATE_ENRICHMENT,
            "observability": RuntimeServiceName.OBSERVABILITY,
        },
    ),
    RuntimeServiceSpec(
        step_name="register_risk",
        callable_name="register_risk",
        service_name=RuntimeServiceName.RISK_ENGINE,
        service_type=RuntimeServiceType.GUARD,
    ),
    RuntimeServiceSpec(
        step_name="register_reward",
        callable_name="register_reward",
        service_name=RuntimeServiceName.REWARD_GUARD,
        service_type=RuntimeServiceType.GUARD,
    ),
    RuntimeServiceSpec(
        step_name="register_simulation",
        callable_name="register_simulation",
        service_name=RuntimeServiceName.SIMULATION_GATE,
        service_type=RuntimeServiceType.GUARD,
    ),
    RuntimeServiceSpec(
        step_name="register_kill_switch",
        callable_name="register_kill_switch",
        service_name=RuntimeServiceName.KILL_SWITCH,
        service_type=RuntimeServiceType.GUARD,
    ),
    RuntimeServiceSpec(
        step_name="register_action_budget",
        callable_name="register_action_budget",
        service_name=RuntimeServiceName.ACTION_BUDGET,
        service_type=RuntimeServiceType.GUARD,
    ),
    RuntimeServiceSpec(
        step_name="register_governance",
        callable_name="register_governance",
        service_name=RuntimeServiceName.GOVERNANCE_CHAIN,
        service_type=RuntimeServiceType.GOVERNANCE,
        dependencies=(
            RuntimeServiceName.RISK_ENGINE,
            RuntimeServiceName.REWARD_GUARD,
            RuntimeServiceName.SIMULATION_GATE,
            RuntimeServiceName.KILL_SWITCH,
            RuntimeServiceName.ACTION_BUDGET,
        ),
    ),
    RuntimeServiceSpec(
        step_name="register_action_executor",
        callable_name="register_action_executor",
        service_name=RuntimeServiceName.ACTION_EXECUTOR,
        service_type=RuntimeServiceType.EXECUTOR,
    ),
    RuntimeServiceSpec(
        step_name="register_decision_core",
        callable_name="register_decision_core",
        service_name=RuntimeServiceName.DECISION_CORE,
        service_type=RuntimeServiceType.CORE,
        dependencies=(
            RuntimeServiceName.GOVERNANCE_CHAIN,
            RuntimeServiceName.ACTION_EXECUTOR,
        ),
    ),
)

RUNTIME_BOOT_SERVICE_SPECS: Final[tuple[RuntimeServiceSpec, ...]] = _RUNTIME_SPECS
RUNTIME_BOOT_SERVICE_SPEC_BY_NAME: Final[dict[str, RuntimeServiceSpec]] = {
    spec.service_name: spec for spec in RUNTIME_BOOT_SERVICE_SPECS
}
RUNTIME_BOOT_SERVICE_SPEC_BY_CALLABLE: Final[dict[str, RuntimeServiceSpec]] = {
    spec.callable_name: spec for spec in RUNTIME_BOOT_SERVICE_SPECS
}
RUNTIME_SERVICE_SPECS: Final[tuple[RuntimeServiceSpec, ...]] = RUNTIME_BOOT_SERVICE_SPECS
RUNTIME_SERVICE_SPEC_BY_NAME: Final[dict[str, RuntimeServiceSpec]] = RUNTIME_BOOT_SERVICE_SPEC_BY_NAME
RUNTIME_SERVICE_SPEC_BY_CALLABLE: Final[dict[str, RuntimeServiceSpec]] = RUNTIME_BOOT_SERVICE_SPEC_BY_CALLABLE
CATALOG_BACKED_RUNTIME_SERVICES: Final[tuple[str, ...]] = tuple(
    spec.service_name
    for spec in RUNTIME_BOOT_SERVICE_SPECS
    if spec.builder_name is not None
)
CATALOG_BACKED_RUNTIME_CALLABLES: Final[tuple[str, ...]] = tuple(
    spec.callable_name
    for spec in RUNTIME_BOOT_SERVICE_SPECS
    if spec.builder_name is not None
)
CATALOG_BACKED_FACTORY_NAMES: Final[dict[str, str]] = {
    spec.service_name: spec.builder_name
    for spec in RUNTIME_BOOT_SERVICE_SPECS
    if spec.builder_name is not None
}
SINGLETON_RUNTIME_CALLABLES: Final[tuple[str, ...]] = tuple(
    spec.callable_name
    for spec in RUNTIME_BOOT_SERVICE_SPECS
    if spec.builder_name is None
    and spec.callable_name not in {"register_action_executor", "register_decision_core", "register_governance"}
)


def get_runtime_service_spec(service_name: str) -> RuntimeServiceSpec:
    try:
        return RUNTIME_BOOT_SERVICE_SPEC_BY_NAME[service_name]
    except KeyError as exc:
        raise KeyError(f"Unknown runtime service spec: {service_name!r}") from exc


def get_runtime_service_spec_by_callable(callable_name: str) -> RuntimeServiceSpec:
    try:
        return RUNTIME_BOOT_SERVICE_SPEC_BY_CALLABLE[callable_name]
    except KeyError as exc:
        raise KeyError(f"Unknown runtime service spec callable: {callable_name!r}") from exc


def get_catalog_factory_name(service_name: str) -> str:
    spec = get_runtime_service_spec(service_name)
    if spec.builder_name is None:
        raise KeyError(f"Runtime service '{service_name}' is not catalog-backed.")
    return spec.builder_name


def build_registration_compat_exports(*, callable_names: tuple[str, ...]) -> dict[str, str]:
    exports: dict[str, str] = {}
    for callable_name in callable_names:
        normalized = str(callable_name).strip()
        if not normalized:
            raise ValueError("registration callable name must not be blank")
        exports[normalized] = normalized
    return exports


__all__ = [
    "CATALOG_BACKED_FACTORY_NAMES",
    "CATALOG_BACKED_RUNTIME_CALLABLES",
    "CATALOG_BACKED_RUNTIME_SERVICES",
    "RUNTIME_BOOT_SERVICE_SPECS",
    "RUNTIME_BOOT_SERVICE_SPEC_BY_CALLABLE",
    "RUNTIME_BOOT_SERVICE_SPEC_BY_NAME",
    "RUNTIME_SERVICE_SPECS",
    "RUNTIME_SERVICE_SPEC_BY_CALLABLE",
    "RUNTIME_SERVICE_SPEC_BY_NAME",
    "RuntimeServiceSpec",
    "SINGLETON_RUNTIME_CALLABLES",
    "build_registration_compat_exports",
    "get_catalog_factory_name",
    "get_runtime_service_spec",
    "get_runtime_service_spec_by_callable",
]

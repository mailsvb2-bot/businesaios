from __future__ import annotations

"""Final owner for runtime service specs.

Physical ownership moved from `boot/*` to `bootstrap/*`.
Legacy boot surfaces remain thin compatibility shells.

This module is the single source of truth for runtime boot ordering,
dependency declarations, and catalog-backed dependency maps. It does not create
a second execution path: the runtime boot manifest remains the only boot
contract consumed by the orchestrator.
"""

from dataclasses import dataclass, field
from typing import Final

from runtime.manifest_entry import RuntimeManifestEntry
from runtime.service_names import RuntimeServiceName, canonical_runtime_service_name
from runtime.service_types import RuntimeServiceType

CANON_RUNTIME_SERVICE_SPECS_FINAL_OWNER = True
CANON_RUNTIME_SERVICE_SPECS_SINGLE_SOURCE = True
CANON_RUNTIME_DECISION_EXECUTION_SERVICE_MANIFEST_NAME = True


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
    RuntimeServiceSpec("register_observability", "register_observability", RuntimeServiceName.OBSERVABILITY, RuntimeServiceType.GUARD),
    RuntimeServiceSpec("register_architecture_watch", "register_architecture_watch", RuntimeServiceName.ARCHITECTURE_WATCH, RuntimeServiceType.GUARD, dependencies=(RuntimeServiceName.OBSERVABILITY,), dependency_map={"observability": RuntimeServiceName.OBSERVABILITY}),
    RuntimeServiceSpec("register_structure_watch", "register_structure_watch", RuntimeServiceName.STRUCTURE_WATCH, RuntimeServiceType.GUARD, dependencies=(RuntimeServiceName.OBSERVABILITY,), dependency_map={"observability": RuntimeServiceName.OBSERVABILITY}),
    RuntimeServiceSpec("register_flow_watch", "register_flow_watch", RuntimeServiceName.FLOW_WATCH, RuntimeServiceType.GUARD, dependencies=(RuntimeServiceName.OBSERVABILITY,), dependency_map={"observability": RuntimeServiceName.OBSERVABILITY}),
    RuntimeServiceSpec("register_diffusion_watch", "register_diffusion_watch", RuntimeServiceName.DIFFUSION_WATCH, RuntimeServiceType.GUARD, dependencies=(RuntimeServiceName.OBSERVABILITY,), dependency_map={"observability": RuntimeServiceName.OBSERVABILITY}),
    RuntimeServiceSpec("register_market_watch", "register_market_watch", RuntimeServiceName.MARKET_WATCH, RuntimeServiceType.GUARD, dependencies=(RuntimeServiceName.OBSERVABILITY,), dependency_map={"observability": RuntimeServiceName.OBSERVABILITY}),
    RuntimeServiceSpec(
        "register_creative_intelligence",
        "register_creative_intelligence",
        RuntimeServiceName.CREATIVE_INTELLIGENCE,
        RuntimeServiceType.GUARD,
        dependencies=(RuntimeServiceName.OBSERVABILITY, RuntimeServiceName.MARKET_WATCH),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        "register_autonomy_advisor",
        "register_autonomy_advisor",
        RuntimeServiceName.AUTONOMY_ADVISOR,
        RuntimeServiceType.GOVERNANCE,
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
        "register_world_state_integration",
        "register_world_state_integration",
        RuntimeServiceName.WORLD_STATE_INTEGRATION,
        RuntimeServiceType.GOVERNANCE,
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
        "register_decision_input_service",
        "register_decision_input_service",
        RuntimeServiceName.DECISION_INPUT_SERVICE,
        RuntimeServiceType.GOVERNANCE,
        dependencies=(RuntimeServiceName.OBSERVABILITY, RuntimeServiceName.WORLD_STATE_INTEGRATION),
        dependency_map={"observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec(
        "register_runtime_packet_provider",
        "register_runtime_packet_provider",
        RuntimeServiceName.RUNTIME_PACKET_PROVIDER,
        RuntimeServiceType.GOVERNANCE,
        dependencies=(RuntimeServiceName.WORLD_STATE_INTEGRATION, RuntimeServiceName.OBSERVABILITY),
        dependency_map={"integration_service": RuntimeServiceName.WORLD_STATE_INTEGRATION, "observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec("register_runtime_state_enrichment", "register_runtime_state_enrichment", RuntimeServiceName.RUNTIME_STATE_ENRICHMENT, RuntimeServiceType.GOVERNANCE, dependencies=(RuntimeServiceName.OBSERVABILITY,), dependency_map={"observability": RuntimeServiceName.OBSERVABILITY}),
    RuntimeServiceSpec(
        "register_decision_gateway",
        "register_decision_gateway",
        RuntimeServiceName.DECISION_GATEWAY,
        RuntimeServiceType.GOVERNANCE,
        dependencies=(RuntimeServiceName.DECISION_INPUT_SERVICE, RuntimeServiceName.RUNTIME_STATE_ENRICHMENT, RuntimeServiceName.OBSERVABILITY),
        dependency_map={"decision_input_service": RuntimeServiceName.DECISION_INPUT_SERVICE, "enrichment_service": RuntimeServiceName.RUNTIME_STATE_ENRICHMENT, "observability": RuntimeServiceName.OBSERVABILITY},
    ),
    RuntimeServiceSpec("register_risk", "register_risk", RuntimeServiceName.RISK_ENGINE, RuntimeServiceType.GUARD),
    RuntimeServiceSpec("register_reward", "register_reward", RuntimeServiceName.REWARD_GUARD, RuntimeServiceType.GUARD),
    RuntimeServiceSpec("register_simulation", "register_simulation", RuntimeServiceName.SIMULATION_GATE, RuntimeServiceType.GUARD),
    RuntimeServiceSpec("register_kill_switch", "register_kill_switch", RuntimeServiceName.KILL_SWITCH, RuntimeServiceType.GUARD),
    RuntimeServiceSpec("register_action_budget", "register_action_budget", RuntimeServiceName.ACTION_BUDGET, RuntimeServiceType.GUARD),
    RuntimeServiceSpec(
        "register_governance",
        "register_governance",
        RuntimeServiceName.GOVERNANCE_CHAIN,
        RuntimeServiceType.GOVERNANCE,
        dependencies=(
            RuntimeServiceName.RISK_ENGINE,
            RuntimeServiceName.REWARD_GUARD,
            RuntimeServiceName.SIMULATION_GATE,
            RuntimeServiceName.KILL_SWITCH,
            RuntimeServiceName.ACTION_BUDGET,
        ),
    ),
    RuntimeServiceSpec("register_action_executor", "register_action_executor", RuntimeServiceName.ACTION_EXECUTOR, RuntimeServiceType.EXECUTOR),
    RuntimeServiceSpec(
        "register_decision_core",
        "register_decision_core",
        RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE,
        RuntimeServiceType.EXECUTOR,
        dependencies=(RuntimeServiceName.GOVERNANCE_CHAIN, RuntimeServiceName.ACTION_EXECUTOR),
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
    spec.service_name for spec in RUNTIME_BOOT_SERVICE_SPECS if spec.builder_name is not None
)
CATALOG_BACKED_RUNTIME_CALLABLES: Final[tuple[str, ...]] = tuple(
    spec.callable_name for spec in RUNTIME_BOOT_SERVICE_SPECS if spec.builder_name is not None
)
CATALOG_BACKED_FACTORY_NAMES: Final[dict[str, str]] = {
    spec.service_name: spec.builder_name for spec in RUNTIME_BOOT_SERVICE_SPECS if spec.builder_name is not None
}
SINGLETON_RUNTIME_CALLABLES: Final[tuple[str, ...]] = tuple(
    spec.callable_name
    for spec in RUNTIME_BOOT_SERVICE_SPECS
    if spec.builder_name is None
    and spec.callable_name not in {"register_action_executor", "register_decision_core", "register_governance"}
)


def get_runtime_service_spec(service_name: str) -> RuntimeServiceSpec:
    canonical_name = canonical_runtime_service_name(service_name)
    try:
        return RUNTIME_BOOT_SERVICE_SPEC_BY_NAME[canonical_name]
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
    "CANON_RUNTIME_DECISION_EXECUTION_SERVICE_MANIFEST_NAME",
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

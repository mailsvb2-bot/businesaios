from __future__ import annotations

"""Final owner for runtime boot surface."""

from dataclasses import dataclass
from collections.abc import Mapping

from bootstrap.bootstrap_config_surface import BootstrapConfigSurface, build_bootstrap_config_surface
from bootstrap.security_boot_surface import SecurityBootSurface, build_security_boot_surface
from observability.alerting_policy import AlertingPolicy
from observability.audit_export_service import AuditExportService
from observability.event_bus import EventBus
from observability.metrics import CounterStore
from observability.sli_collector import SLICollector
from observability.tenant_metrics_registry import TenantMetricsRegistry
from observability.tracing import Tracer
from runtime.runtime_orchestrator import RuntimeOrchestrator
from shared.registry import ComponentRegistry, ServiceRegistry

from boot.observability_boot import ObservabilitySurface, build_observability_surface

CANON_RUNTIME_BOOT_FINAL_OWNER = True
CANON_RUNTIME_BOOT_SURFACE = True
CANON_RUNTIME_BOOT_FACTORY = True
CANON_RUNTIME_BOOT_INTERNAL_SURFACE = True
CANON_RUNTIME_BOOT_NO_PUBLIC_ENTRYPOINT = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"


@dataclass(frozen=True)
class RuntimeBootSurface:
    orchestrator: RuntimeOrchestrator
    service_names: tuple[str, ...]
    component_names: tuple[str, ...]
    config_surface: BootstrapConfigSurface
    observability_surface: ObservabilitySurface
    security_surface: SecurityBootSurface

    def shared_observability_payload(self) -> dict[str, object]:
        return {**dict(self.orchestrator.services.items()), **dict(self.orchestrator.components.items())}

    def shared_runtime_payload(self) -> dict[str, object]:
        return {**self.shared_observability_payload(), **self.security_surface.shared_runtime_payload()}

    def observability_snapshot(self) -> dict[str, object]:
        snapshot = {
            "event_bus": type(self.orchestrator.services.get("event_bus")).__name__,
            "metrics": type(self.orchestrator.services.get("metrics")).__name__,
            "tracer": type(self.orchestrator.services.get("tracer")).__name__,
            "tenant_metrics_registry": type(self.orchestrator.services.get("tenant_metrics_registry")).__name__,
            "audit_export_service": type(self.orchestrator.services.get("audit_export_service")).__name__,
            "telemetry_event_store": type(self.orchestrator.services.get("telemetry_event_store")).__name__,
            "decision_audit_log": type(self.orchestrator.components.get("decision_audit_log")).__name__,
            "action_audit_log": type(self.orchestrator.components.get("action_audit_log")).__name__,
            "execution_trace_store": type(self.orchestrator.components.get("execution_trace_store")).__name__,
            "decision_trace_store": type(self.orchestrator.components.get("decision_trace_store")).__name__,
            "runtime_effect_trace_store": type(self.orchestrator.components.get("runtime_effect_trace_store")).__name__,
            "sli_collector": type(self.orchestrator.components.get("sli_collector")).__name__,
            "alerting_policy": type(self.orchestrator.components.get("alerting_policy")).__name__,
            "incident_signal_store": type(self.orchestrator.components.get("incident_signal_store")).__name__,
        }
        snapshot["config"] = self.config_surface.snapshot()
        snapshot["security"] = self.security_surface.snapshot()
        return snapshot


_SERVICE_TYPES: tuple[tuple[str, type[object]], ...] = (
    ("event_bus", EventBus),
    ("metrics", CounterStore),
    ("tracer", Tracer),
    ("tenant_metrics_registry", TenantMetricsRegistry),
    ("audit_export_service", AuditExportService),
    ("telemetry_event_store", object),
)
_COMPONENT_NAMES: tuple[str, ...] = (
    "decision_audit_log",
    "action_audit_log",
    "execution_trace_store",
    "decision_trace_store",
    "runtime_effect_trace_store",
    "incident_signal_store",
    "sli_collector",
    "alerting_policy",
)


def _build_service_registry(*, services_payload: Mapping[str, object]) -> ServiceRegistry:
    services = ServiceRegistry()
    for name, _ in _SERVICE_TYPES:
        if name in services_payload:
            services.register(name, services_payload[name])
    return services


def _build_component_registry(*, components_payload: Mapping[str, object]) -> ComponentRegistry:
    components = ComponentRegistry()
    for name in _COMPONENT_NAMES:
        if name in components_payload:
            components.register(name, components_payload[name])
    return components


def build_runtime_boot_surface(
    *,
    config_surface: BootstrapConfigSurface | None = None,
    observability_surface: ObservabilitySurface | None = None,
    security_surface: SecurityBootSurface | None = None,
) -> RuntimeBootSurface:
    resolved_config_surface = config_surface or build_bootstrap_config_surface()
    resolved_observability_surface = observability_surface or build_observability_surface(config_surface=resolved_config_surface)
    resolved_security_surface = security_surface or build_security_boot_surface(config_surface=resolved_config_surface)
    services_payload = dict(resolved_observability_surface.services)
    components_payload = dict(resolved_observability_surface.components)
    orchestrator = RuntimeOrchestrator(
        services=_build_service_registry(services_payload=services_payload),
        components=_build_component_registry(components_payload=components_payload),
    )
    return RuntimeBootSurface(
        orchestrator=orchestrator,
        service_names=tuple(orchestrator.services.keys()),
        component_names=tuple(orchestrator.components.keys()),
        config_surface=resolved_config_surface,
        observability_surface=resolved_observability_surface,
        security_surface=resolved_security_surface,
    )


def build_runtime_orchestrator(
    *,
    config_surface: BootstrapConfigSurface | None = None,
    observability_surface: ObservabilitySurface | None = None,
    security_surface: SecurityBootSurface | None = None,
) -> RuntimeOrchestrator:
    return build_runtime_boot_surface(
        config_surface=config_surface,
        observability_surface=observability_surface,
        security_surface=security_surface,
    ).orchestrator


__all__ = [
    "CANON_RUNTIME_BOOT_FACTORY",
    "CANON_RUNTIME_BOOT_FINAL_OWNER",
    "CANON_RUNTIME_BOOT_INTERNAL_SURFACE",
    "CANON_RUNTIME_BOOT_NO_PUBLIC_ENTRYPOINT",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "RuntimeBootSurface",
    "build_runtime_boot_surface",
    "build_runtime_orchestrator",
]

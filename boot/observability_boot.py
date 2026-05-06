from __future__ import annotations

import os

from boot.bootstrap_config_surface import BootstrapConfigSurface, build_bootstrap_config_surface
from runtime.service_names import RuntimeServiceName
from dataclasses import dataclass
from pathlib import Path

from observability.action_audit_log import ActionAuditLog, build_default_action_audit_log
from observability.alerting_policy import AlertingPolicy
from observability.audit_export_service import AuditExportService
from observability.decision_audit_log import DecisionAuditLog, build_default_decision_audit_log
from observability.decision_trace_store import InMemoryDecisionTraceStore, PersistentDecisionTraceStore
from observability.event_bus import EventBus
from observability.execution_trace_store import InMemoryExecutionTraceStore, PersistentExecutionTraceStore
from observability.incident_signal_store import InMemoryIncidentSignalStore, PersistentIncidentSignalStore
from observability.metrics import CounterStore
from observability.platform.telemetry.event_store import build_default_event_store
from observability.runtime_effect_trace_store import InMemoryRuntimeEffectTraceStore, PersistentRuntimeEffectTraceStore
from observability.sli_collector import SLICollector
from observability.tenant_metrics_registry import TenantMetricsRegistry
from observability.tracing import Tracer

CANON_BOOT_HELPER_SURFACE = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"
CANON_OBSERVABILITY_BOOT_FACTORY = True


def _store_mode(config_surface: BootstrapConfigSurface) -> str:
    return config_surface.observability_store_mode


def _persistent_dir(config_surface: BootstrapConfigSurface) -> Path:
    return config_surface.observability_data_dir


def _build_execution_trace_store(config_surface: BootstrapConfigSurface) -> object:
    if _store_mode(config_surface) == "persistent":
        return PersistentExecutionTraceStore(path=config_surface.execution_trace_store_path, config_surface=config_surface)
    return InMemoryExecutionTraceStore()


def _build_decision_trace_store(config_surface: BootstrapConfigSurface) -> object:
    if _store_mode(config_surface) == "persistent":
        return PersistentDecisionTraceStore(path=config_surface.decision_trace_store_path, config_surface=config_surface)
    return InMemoryDecisionTraceStore()


def _build_runtime_effect_trace_store(config_surface: BootstrapConfigSurface) -> object:
    if _store_mode(config_surface) == "persistent":
        return PersistentRuntimeEffectTraceStore(path=config_surface.runtime_effect_trace_store_path, config_surface=config_surface)
    return InMemoryRuntimeEffectTraceStore()


def _build_incident_signal_store(config_surface: BootstrapConfigSurface) -> object:
    if _store_mode(config_surface) == "persistent":
        return PersistentIncidentSignalStore(path=config_surface.incident_signal_store_path, config_surface=config_surface)
    return InMemoryIncidentSignalStore()


@dataclass(frozen=True)
class ObservabilitySurface:
    services: dict[str, object]
    components: dict[str, object]
    config_surface: BootstrapConfigSurface

    def payload(self) -> dict[str, object]:
        return {**self.services, **self.components}


def build_observability_surface(*, config_surface: BootstrapConfigSurface | None = None) -> ObservabilitySurface:
    resolved_config_surface = config_surface or build_bootstrap_config_surface()
    tenant_metrics_registry = TenantMetricsRegistry()
    services = {
        "event_bus": EventBus(),
        "metrics": CounterStore(),
        "tracer": Tracer(),
        "tenant_metrics_registry": tenant_metrics_registry,
        "audit_export_service": AuditExportService(config_surface=resolved_config_surface),
        "telemetry_event_store": build_default_event_store(config_surface=resolved_config_surface),
    }
    components = {
        "decision_audit_log": build_default_decision_audit_log(config_surface=resolved_config_surface),
        "action_audit_log": build_default_action_audit_log(config_surface=resolved_config_surface),
        "execution_trace_store": _build_execution_trace_store(resolved_config_surface),
        "decision_trace_store": _build_decision_trace_store(resolved_config_surface),
        "runtime_effect_trace_store": _build_runtime_effect_trace_store(resolved_config_surface),
        "audit_export_service": services["audit_export_service"],
        "tenant_metrics_registry": tenant_metrics_registry,
        "sli_collector": SLICollector(metrics_registry=tenant_metrics_registry),
        "alerting_policy": AlertingPolicy(metrics_registry=tenant_metrics_registry),
        "incident_signal_store": _build_incident_signal_store(resolved_config_surface),
    }
    # Keep payload complete for callers that expect a flat dict while preserving
    # a single canonical owner for observability assembly.
    components.pop("audit_export_service")
    components.pop("tenant_metrics_registry")
    return ObservabilitySurface(services=services, components=components, config_surface=resolved_config_surface)


def load_observability(*, config_surface: BootstrapConfigSurface | None = None) -> dict[str, object]:
    return build_observability_surface(config_surface=config_surface).payload()

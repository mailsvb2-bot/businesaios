from __future__ import annotations

from typing import Any

REQUIRED_OBSERVABILITY_KEYS = (
    "action_audit_log",
    "decision_audit_log",
    "event_bus",
    "metrics",
    "tracer",
    "tenant_metrics_registry",
    "audit_export_service",
    "telemetry_event_store",
    "execution_trace_store",
    "decision_trace_store",
    "runtime_effect_trace_store",
    "sli_collector",
    "alerting_policy",
    "incident_signal_store",
)


def runtime_observability_snapshot(*, boot_payload: dict[str, Any], runtime_orchestrator: object) -> dict[str, str]:
    services = getattr(runtime_orchestrator, "services")
    components = getattr(runtime_orchestrator, "components")
    return {
        "event_bus": type(boot_payload["event_bus"]).__name__,
        "metrics": type(boot_payload["metrics"]).__name__,
        "tracer": type(boot_payload["tracer"]).__name__,
        "tenant_metrics_registry": type(boot_payload["tenant_metrics_registry"]).__name__,
        "audit_export_service": type(boot_payload["audit_export_service"]).__name__,
        "decision_audit_log": type(boot_payload["decision_audit_log"]).__name__,
        "action_audit_log": type(boot_payload["action_audit_log"]).__name__,
        "execution_trace_store": type(boot_payload["execution_trace_store"]).__name__,
        "decision_trace_store": type(boot_payload["decision_trace_store"]).__name__,
        "runtime_effect_trace_store": type(boot_payload["runtime_effect_trace_store"]).__name__,
        "sli_collector": type(boot_payload["sli_collector"]).__name__,
        "alerting_policy": type(boot_payload["alerting_policy"]).__name__,
        "incident_signal_store": type(boot_payload["incident_signal_store"]).__name__,
        "runtime_service_event_bus": type(services.get("event_bus")).__name__,
        "runtime_service_metrics": type(services.get("metrics")).__name__,
        "runtime_service_tracer": type(services.get("tracer")).__name__,
        "runtime_service_tenant_metrics_registry": type(services.get("tenant_metrics_registry")).__name__,
        "runtime_service_audit_export_service": type(services.get("audit_export_service")).__name__,
        "runtime_component_decision_audit_log": type(components.get("decision_audit_log")).__name__,
        "runtime_component_action_audit_log": type(components.get("action_audit_log")).__name__,
        "runtime_component_execution_trace_store": type(components.get("execution_trace_store")).__name__,
        "runtime_component_decision_trace_store": type(components.get("decision_trace_store")).__name__,
        "runtime_component_runtime_effect_trace_store": type(components.get("runtime_effect_trace_store")).__name__,
        "runtime_component_sli_collector": type(components.get("sli_collector")).__name__,
        "runtime_component_alerting_policy": type(components.get("alerting_policy")).__name__,
        "runtime_component_incident_signal_store": type(components.get("incident_signal_store")).__name__,
    }

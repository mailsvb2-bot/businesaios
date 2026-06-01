from __future__ import annotations

from boot.observability_boot import load_observability
from boot.runtime_boot import build_runtime_boot_surface, build_runtime_orchestrator
from formal.regression_gate.observability_contract import REQUIRED_OBSERVABILITY_KEYS


def test_runtime_boot_builds_fresh_stateful_observability_instances() -> None:
    first = build_runtime_orchestrator()
    second = build_runtime_orchestrator()
    assert first.services.get("tenant_metrics_registry") is not second.services.get("tenant_metrics_registry")
    assert first.components.get("execution_trace_store") is not second.components.get("execution_trace_store")
    assert first.components.get("incident_signal_store") is not second.components.get("incident_signal_store")


def test_runtime_boot_surface_contains_enterprise_observability_components() -> None:
    surface = build_runtime_boot_surface()
    assert "execution_trace_store" in surface.component_names
    assert "decision_trace_store" in surface.component_names
    assert "runtime_effect_trace_store" in surface.component_names
    assert "incident_signal_store" in surface.component_names
    assert "tenant_metrics_registry" in surface.service_names
    assert "audit_export_service" in surface.service_names


def test_boot_payload_keeps_full_observability_contract() -> None:
    payload = load_observability()
    assert tuple(sorted(REQUIRED_OBSERVABILITY_KEYS)) == tuple(sorted(payload.keys()))

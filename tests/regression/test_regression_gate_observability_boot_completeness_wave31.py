from __future__ import annotations

from boot.observability_boot import load_observability
from boot.runtime_boot import build_runtime_orchestrator
from formal.regression_gate.observability_contract import REQUIRED_OBSERVABILITY_KEYS, runtime_observability_snapshot


def test_boot_and_runtime_observability_surfaces_are_complete() -> None:
    boot_payload = load_observability()
    runtime_orchestrator = build_runtime_orchestrator()
    for key in REQUIRED_OBSERVABILITY_KEYS:
        assert key in boot_payload
    snapshot = runtime_observability_snapshot(boot_payload=boot_payload, runtime_orchestrator=runtime_orchestrator)
    assert snapshot["event_bus"] == snapshot["runtime_service_event_bus"]
    assert snapshot["metrics"] == snapshot["runtime_service_metrics"]
    assert snapshot["tracer"] == snapshot["runtime_service_tracer"]
    assert snapshot["tenant_metrics_registry"] == snapshot["runtime_service_tenant_metrics_registry"]
    assert snapshot["audit_export_service"] == snapshot["runtime_service_audit_export_service"]
    assert snapshot["decision_audit_log"] == snapshot["runtime_component_decision_audit_log"]
    assert snapshot["action_audit_log"] == snapshot["runtime_component_action_audit_log"]
    assert snapshot["execution_trace_store"] == snapshot["runtime_component_execution_trace_store"]
    assert snapshot["decision_trace_store"] == snapshot["runtime_component_decision_trace_store"]
    assert snapshot["runtime_effect_trace_store"] == snapshot["runtime_component_runtime_effect_trace_store"]
    assert snapshot["sli_collector"] == snapshot["runtime_component_sli_collector"]
    assert snapshot["alerting_policy"] == snapshot["runtime_component_alerting_policy"]
    assert snapshot["incident_signal_store"] == snapshot["runtime_component_incident_signal_store"]

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_FILES = (
    "observability/execution_trace_contract.py",
    "observability/execution_trace_store.py",
    "observability/decision_trace_store.py",
    "observability/runtime_effect_trace_store.py",
    "observability/audit_event_schema.py",
    "observability/audit_export_service.py",
    "observability/alert_rule_contract.py",
    "observability/alerting_policy.py",
    "observability/slo_contract.py",
    "observability/sli_collector.py",
    "observability/incident_signal_store.py",
    "observability/tenant_metrics_registry.py",
)
FORBIDDEN_IMPORT_MARKERS = (
    "DecisionCore",
    "core.ai.decision_core",
    "core.decision",
    "business policy",
    "selected by policy engine",
)


def test_enterprise_observability_modules_do_not_embed_second_brain_logic() -> None:
    offenders: list[str] = []
    for rel in OBSERVABILITY_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if any(marker in text for marker in FORBIDDEN_IMPORT_MARKERS):
            offenders.append(rel)
    assert offenders == []

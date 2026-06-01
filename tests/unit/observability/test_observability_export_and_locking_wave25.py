from __future__ import annotations

from observability.action_audit_log import FileActionAuditLog
from observability.audit_export_service import AuditExportService
from observability.decision_audit_log import FileDecisionAuditLog
from observability.decision_trace_store import PersistentDecisionTraceStore
from observability.execution_trace_contract import (
    DecisionTraceEvent,
    EffectDisposition,
    ExecutionTraceEvent,
    RuntimeEffectTraceEvent,
    TraceStage,
)
from observability.execution_trace_store import PersistentExecutionTraceStore
from observability.incident_signal_store import IncidentSignalRecord, PersistentIncidentSignalStore
from observability.runtime_effect_trace_store import PersistentRuntimeEffectTraceStore
from observability.trace_storage_policy import TraceStoragePolicy


def test_export_observability_bundle_includes_segment_manifests(tmp_path) -> None:
    export_service = AuditExportService()
    execution_store = PersistentExecutionTraceStore(
        path=tmp_path / "execution_trace.jsonl",
        storage_policy=TraceStoragePolicy(max_records_per_segment=1, max_bytes_per_segment=10_000, backup_count=2),
    )
    decision_store = PersistentDecisionTraceStore(
        path=tmp_path / "decision_trace.jsonl",
        storage_policy=TraceStoragePolicy(max_records_per_segment=1, max_bytes_per_segment=10_000, backup_count=2),
    )
    effect_store = PersistentRuntimeEffectTraceStore(
        path=tmp_path / "runtime_effect_trace.jsonl",
        storage_policy=TraceStoragePolicy(max_records_per_segment=1, max_bytes_per_segment=10_000, backup_count=2),
    )
    for idx in range(3):
        execution_store.append(ExecutionTraceEvent(tenant_id="tenant-a", trace_id="trace-1", run_id="run-1", sequence_no=idx, stage=TraceStage.EXECUTION, event_type=f"exec-{idx}"))
        decision_store.append(DecisionTraceEvent(tenant_id="tenant-a", trace_id="trace-1", decision_id=f"d-{idx}", selected_action="launch", candidate_count=1))
        effect_store.append(RuntimeEffectTraceEvent(tenant_id="tenant-a", trace_id="trace-1", effect_id=f"e-{idx}", effect_type="email.send", disposition=EffectDisposition.SUCCEEDED))

    bundle = export_service.export_observability_bundle(
        stores={
            "execution": execution_store,
            "decision": decision_store,
            "effect": effect_store,
        }
    )

    assert bundle["stores"]["execution"]["backend"] == "PersistentExecutionTraceStore"
    assert len(bundle["stores"]["execution"]["segments"]) >= 2
    assert bundle["stores"]["decision"]["segments"][0]["filename"].startswith("decision_trace.jsonl")


def test_file_backed_audit_logs_use_locking_without_leaving_lock_artifacts(tmp_path) -> None:
    action_log = FileActionAuditLog(path=tmp_path / "action_audit_log.json")
    decision_log = FileDecisionAuditLog(path=tmp_path / "decision_audit_log.json")

    action_log.record({"tenant_id": "tenant-a", "action_id": "a-1", "action_type": "launch", "status": "ok"})
    decision_log.record_payload({"tenant_id": "tenant-a", "decision_id": "d-1", "trace_id": "trace-1"})

    assert action_log.path.exists()
    assert decision_log.path.exists()
    assert not action_log.path.with_suffix(action_log.path.suffix + ".lock").exists()
    assert not decision_log.path.with_suffix(decision_log.path.suffix + ".lock").exists()


def test_persistent_incident_signal_store_rotates_and_exports_segments(tmp_path) -> None:
    export_service = AuditExportService()
    store = PersistentIncidentSignalStore(path=tmp_path / "incident_signals.json")
    # shrink policy after construction for deterministic rotation without changing public API
    object.__setattr__(store, "_storage_policy", store.storage_policy.__class__(max_records=1, max_bytes=1, backup_count=2))

    for idx in range(3):
        store.append(IncidentSignalRecord(incident_id=f"i-{idx}", tenant_id="tenant-a", signal_type="quota", summary=f"signal-{idx}"))

    bundle = export_service.export_observability_bundle(stores={"incidents": store})

    assert bundle["stores"]["incidents"]["backend"] == "PersistentIncidentSignalStore"
    assert len(bundle["stores"]["incidents"]["segments"]) >= 2
    assert not store.path.with_suffix(store.path.suffix + ".lock").exists()

from __future__ import annotations

from observability.audit_export_service import AuditExportService
from observability.action_audit_log import FileActionAuditLog
from observability.decision_audit_log import FileDecisionAuditLog


def test_observability_bundle_contains_metadata_summary(tmp_path) -> None:
    action_log = FileActionAuditLog(path=tmp_path / "action_audit_log.json")
    decision_log = FileDecisionAuditLog(path=tmp_path / "decision_audit_log.json")
    action_log.record({"tenant_id": "tenant-a", "action_id": "a-1", "action_type": "launch", "status": "ok"})
    decision_log.record_payload({"tenant_id": "tenant-a", "decision_id": "d-1", "trace_id": "trace-1"})
    bundle = AuditExportService().export_observability_bundle(stores={"action": action_log, "decision": decision_log})
    metadata = bundle["metadata"]
    assert metadata["store_count"] == 2
    assert metadata["segment_count"] >= 2
    assert metadata["existing_segment_count"] >= 2
    assert metadata["total_bytes"] > 0
    assert len(metadata["stores_sha256"]) == 64


def test_compliance_bundle_contains_generated_at_and_counts() -> None:
    bundle = AuditExportService().export_compliance_bundle(tenant_id="tenant-a", audit_events=[], incidents=[])
    assert bundle["tenant_id"] == "tenant-a"
    assert bundle["generated_at"]
    assert bundle["metadata"]["audit_event_count"] == 0
    assert bundle["metadata"]["incident_count"] == 0

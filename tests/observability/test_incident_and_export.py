from __future__ import annotations

from observability.audit_event_schema import AuditCategory, AuditEventRecord, AuditSeverity
from observability.audit_export_service import AuditExportService
from observability.incident_signal_store import InMemoryIncidentSignalStore, IncidentSignalRecord, IncidentStatus


TENANT_ID = "tenant-a"


def test_incident_signal_store_deduplicates_open_incident_by_dedup_key() -> None:
    store = InMemoryIncidentSignalStore()
    first = store.upsert_open_by_dedup_key(
        IncidentSignalRecord(
            incident_id="incident-1",
            tenant_id=TENANT_ID,
            signal_type="alert.match",
            dedup_key="tenant-a:error-rate-high",
            summary="first",
        )
    )
    second = store.upsert_open_by_dedup_key(
        IncidentSignalRecord(
            incident_id="incident-2",
            tenant_id=TENANT_ID,
            signal_type="alert.match",
            dedup_key="tenant-a:error-rate-high",
            summary="updated",
        )
    )
    assert first.incident_id == second.incident_id
    assert second.summary == "updated"
    assert len(store.list_open(tenant_id=TENANT_ID)) == 1
    resolved = store.resolve(tenant_id=TENANT_ID, incident_id=second.incident_id)
    assert resolved.status is IncidentStatus.RESOLVED


def test_audit_export_service_exports_compliance_bundle() -> None:
    exporter = AuditExportService()
    audit_event = AuditEventRecord(
        audit_id="audit-1",
        tenant_id=TENANT_ID,
        event_type="runtime.booted",
        category=AuditCategory.OPERATIONS,
        severity=AuditSeverity.INFO,
    )
    incident = IncidentSignalRecord(
        incident_id="incident-1",
        tenant_id=TENANT_ID,
        signal_type="alert.match",
        summary="runtime boot incident",
    )
    bundle = exporter.export_compliance_bundle(
        tenant_id=TENANT_ID,
        audit_events=[audit_event],
        incidents=[incident],
    )
    assert bundle["tenant_id"] == TENANT_ID
    assert len(bundle["audit_events"]) == 1
    assert len(bundle["incidents"]) == 1

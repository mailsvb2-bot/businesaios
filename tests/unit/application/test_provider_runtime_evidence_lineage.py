from __future__ import annotations

from runtime.business_autonomy.provider_runtime_audit import ProviderRuntimeAuditRecorder


def test_provider_runtime_audit_emits_canonical_evidence_lineage() -> None:
    recorder = ProviderRuntimeAuditRecorder.in_memory()
    refs = recorder.record_sync_run(
        tenant_id="tenant-a",
        business_id="business-a",
        provider_key="shopify",
        operation="catalog_sync",
        mode="live",
        status="completed",
        accepted=True,
        payload={"cursor": "1"},
        metadata={"items": 3},
    )
    record = recorder.evidence_store.get(tenant_id="tenant-a", evidence_id=refs["evidence_id"])
    assert record is not None
    assert record.business_id == "business-a"
    assert record.source == "shopify"
    assert record.source_type == "provider_sync"
    assert record.observed_at is not None
    assert record.retention_policy == "provider_runtime_evidence"
    assert dict(record.lineage)["source"] == "provider:shopify"
    assert dict(record.lineage)["normalization"] == refs["audit_event_id"]
    assert dict(record.lineage)["action"] == "business-a:shopify:catalog_sync"


def test_business_autonomy_boot_wires_provider_runtime_to_durable_canonical_stores(monkeypatch, tmp_path) -> None:
    from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service
    from storage.audit_store import SqliteAuditStore
    from storage.audit_wiring import build_canonical_audit_store
    from storage.evidence_store import SqliteEvidenceStore
    from storage.evidence_wiring import build_canonical_evidence_store

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    service = build_business_autonomy_guarded_service(business_id="provider-evidence-wiring")
    recorder = service._provider_admin_service.audit_recorder
    assert isinstance(recorder.audit_store, SqliteAuditStore)
    assert isinstance(recorder.evidence_store, SqliteEvidenceStore)

    refs = recorder.record_sync_run(
        tenant_id="tenant-a", business_id="business-a", provider_key="shopify",
        operation="catalog_sync", mode="dry_run", status="dry_run_ready", accepted=True,
        payload={"cursor": "1"}, metadata={"items": 1},
    )

    reopened_audit = build_canonical_audit_store()
    reopened_evidence = build_canonical_evidence_store()
    assert reopened_audit.get(refs["audit_event_id"]) is not None
    persisted = reopened_evidence.get(tenant_id="tenant-a", evidence_id=refs["evidence_id"])
    assert persisted is not None
    assert persisted.source_type == "provider_sync"


def test_provider_runtime_evidence_preserves_verified_decision_provenance() -> None:
    recorder = ProviderRuntimeAuditRecorder.in_memory()
    provenance = {
        "source": "owner_decision_draft",
        "verification": "server_ledger",
        "tenant_id": "tenant-a",
        "business_id": "business-a",
        "run_id": "run-owner-1",
        "decision_id": "decision-owner-1",
        "action_id": "action-owner-1",
        "action_type": "send_message@v1",
    }
    refs = recorder.record_sync_run(
        tenant_id="tenant-a",
        business_id="business-a",
        provider_key="vk_messaging",
        operation="message_send",
        mode="live",
        status="live_executed",
        accepted=True,
        payload={"peer_id": "42"},
        metadata={"decision_provenance": provenance, "parsed_response": {"resource_id": "77"}},
    )

    record = recorder.evidence_store.get(tenant_id="tenant-a", evidence_id=refs["evidence_id"])
    assert record is not None
    assert record.run_id == "run-owner-1"
    assert record.action_id == "action-owner-1"
    assert record.lineage["decision"] == "decision-owner-1"
    assert record.lineage["action"] == "action-owner-1"
    assert record.lineage["outcome"] == "business-a:vk_messaging:message_send:live_executed"
    assert record.refs == (
        refs["audit_event_id"],
        "run-owner-1",
        "decision-owner-1",
        "action-owner-1",
    )
    assert record.labels["decision_id"] == "decision-owner-1"


def test_provider_runtime_evidence_rejects_cross_scope_decision_provenance() -> None:
    recorder = ProviderRuntimeAuditRecorder.in_memory()
    provenance = {
        "source": "owner_decision_draft",
        "verification": "server_ledger",
        "tenant_id": "tenant-other",
        "business_id": "business-other",
        "run_id": "run-owner-1",
        "decision_id": "decision-owner-1",
        "action_id": "action-owner-1",
        "action_type": "send_message@v1",
    }

    import pytest

    with pytest.raises(ValueError, match="provenance scope mismatch"):
        recorder.record_sync_run(
            tenant_id="tenant-a",
            business_id="business-a",
            provider_key="vk_messaging",
            operation="message_send",
            mode="live",
            status="live_executed",
            accepted=True,
            payload={"peer_id": "42"},
            metadata={"decision_provenance": provenance},
        )

    assert recorder.evidence_store.list_for_tenant(tenant_id="tenant-a") == ()

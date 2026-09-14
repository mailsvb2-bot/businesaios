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
    record = recorder.evidence_store.get(refs["evidence_id"])
    assert record is not None
    assert record.business_id == "business-a"
    assert record.source == "shopify"
    assert record.source_type == "provider_sync"
    assert record.retention_policy == "provider_runtime_evidence"
    assert dict(record.lineage)["source"] == "provider:shopify"
    assert dict(record.lineage)["normalization"] == refs["audit_event_id"]
    assert dict(record.lineage)["action"] == "business-a:shopify:catalog_sync"

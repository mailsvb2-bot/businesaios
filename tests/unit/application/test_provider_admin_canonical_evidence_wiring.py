from __future__ import annotations

from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service
from storage.evidence_wiring import build_canonical_evidence_store


def _service(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    root = build_business_autonomy_guarded_service(business_id="provider-evidence-wiring")
    return root._provider_admin_service


def test_provider_admin_sync_persists_through_injected_canonical_recorder(monkeypatch, tmp_path) -> None:
    service = _service(monkeypatch, tmp_path)
    result = service.trigger_provider_sync(
        tenant_id="tenant-a", business_id="shop-a", provider_key="shopify",
        operation="catalog_sync", mode="dry_run", payload={"cursor": "1"},
    )
    assert result["status"]
    rows = build_canonical_evidence_store().list_for_tenant(tenant_id="tenant-a")
    assert any(row.source_type == "provider_sync" and row.business_id == "shop-a" for row in rows)


def test_provider_admin_webhook_persists_through_injected_canonical_recorder(monkeypatch, tmp_path) -> None:
    service = _service(monkeypatch, tmp_path)
    result = service.ingest_provider_webhook(
        tenant_id="tenant-a", business_id="shop-a", provider_key="shopify",
        headers={}, body=b'{"id":11}', event_key="evt-11", topic="orders/create",
    )
    assert result["status"]
    rows = build_canonical_evidence_store().list_for_tenant(tenant_id="tenant-a")
    assert any(row.source_type == "provider_webhook" and row.business_id == "shop-a" for row in rows)

from __future__ import annotations

import pytest

from application.business_autonomy.provider_admin_contract import ProviderActivationStatus
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore


def _status(**overrides) -> ProviderActivationStatus:
    values = {
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "provider_key": "telegram_messaging",
        "connected": True,
        "connector_id": "messaging.telegram",
        "title": "Telegram",
        "channel_kind": "chatbot",
        "secret_fields_bound": ("bot_token",),
        "last_updated_utc": "2026-09-15T00:00:00+00:00",
        "governance_enabled": True,
        "persistent_surfaces": ("provider_activation",),
        "onboarding_ready": True,
        "metadata": {},
    }
    values.update(overrides)
    return ProviderActivationStatus(**values)


def test_provider_activation_store_round_trips_scoped_status(tmp_path) -> None:
    store = FileProviderActivationStore(FileDistributedDocumentStore(tmp_path / "documents"))
    saved = store.put(_status())
    assert saved.tenant_id == "tenant-1"
    assert saved.business_id == "business-1"
    assert saved.provider_key == "telegram_messaging"
    assert store.get(
        tenant_id="tenant-1", business_id="business-1", provider_key="telegram_messaging"
    ) == saved


def test_provider_activation_store_rejects_empty_business_or_provider_scope(tmp_path) -> None:
    store = FileProviderActivationStore(FileDistributedDocumentStore(tmp_path / "documents"))
    with pytest.raises(ValueError, match="business_id is required"):
        store.put(_status(business_id=""))
    with pytest.raises(ValueError, match="provider_key is required"):
        store.put(_status(provider_key=""))
    with pytest.raises(ValueError, match="business_id is required"):
        store.get(tenant_id="tenant-1", business_id="", provider_key="telegram_messaging")
    with pytest.raises(ValueError, match="provider_key is required"):
        store.get(tenant_id="tenant-1", business_id="business-1", provider_key="")


def test_provider_activation_store_fails_closed_on_corrupt_persisted_scope(tmp_path) -> None:
    documents = FileDistributedDocumentStore(tmp_path / "documents")
    documents.put(
        collection="provider_activation_state",
        document_id="tenant-1:business-1:telegram_messaging",
        payload={
            "tenant_id": "tenant-1",
            "business_id": "business-1",
            "provider_key": "",
            "connected": False,
        },
    )
    store = FileProviderActivationStore(documents)
    with pytest.raises(ValueError, match="provider_key is required"):
        store.get(
            tenant_id="tenant-1", business_id="business-1", provider_key="telegram_messaging"
        )

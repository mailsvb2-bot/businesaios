from __future__ import annotations

import pytest

from application.business_autonomy.provider_admin_contract import ProviderActivationStatus
from contracts.event_store import canonical_business_event_contract
from core.events.event_types import PROVIDER_CREATED, PROVIDER_UPDATED
from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore
from runtime.business_autonomy.provider_activation_store import FileProviderActivationStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


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
    with pytest.raises(ValueError, match="business_id is required"):
        store.list_for_business(tenant_id="tenant-1", business_id="")


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

def test_provider_activation_store_rejects_durable_scope_rebinding_before_event_projection(tmp_path) -> None:
    documents = FileDistributedDocumentStore(tmp_path / "documents")
    events = MemoryEventStore()
    foreign = _status(business_id="business-2")
    documents.put(
        collection="provider_activation_state",
        document_id="tenant-1:business-1:telegram_messaging",
        payload=FileProviderActivationStore._status_payload(foreign),
    )
    store = FileProviderActivationStore(documents, event_store=events)

    with pytest.raises(RuntimeError, match="PROVIDER_ACTIVATION_SCOPE_MISMATCH"):
        store.get(
            tenant_id="tenant-1",
            business_id="business-1",
            provider_key="telegram_messaging",
        )
    with pytest.raises(RuntimeError, match="PROVIDER_ACTIVATION_SCOPE_MISMATCH"):
        store.list_for_business(tenant_id="tenant-1", business_id="business-1")
    with pytest.raises(RuntimeError, match="PROVIDER_ACTIVATION_SCOPE_MISMATCH"):
        store.put(_status())

    assert list(
        events.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=PROVIDER_CREATED,
        )
    ) == []


class _FailOnceEventStore:
    def __init__(self) -> None:
        self.inner = MemoryEventStore()
        self.fail_once = True

    def append_event(self, event) -> None:
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("simulated provider event append failure")
        self.inner.append_event(event)

    def iter_events(self, **kwargs):
        return self.inner.iter_events(**kwargs)


def test_provider_activation_projects_created_and_updated_without_secret_metadata(tmp_path) -> None:
    events = MemoryEventStore()
    store = FileProviderActivationStore(
        FileDistributedDocumentStore(tmp_path / "documents"),
        event_store=events,
    )
    created = store.put(_status(metadata={"secret_value": "must-not-project"}))
    created_rows = list(
        events.iter_events(
            tenant_id=created.tenant_id,
            start_ms=0,
            event_type=PROVIDER_CREATED,
        )
    )
    assert len(created_rows) == 1
    created_event = canonical_business_event_contract(created_rows[0])
    assert created_event["business_id"] == created.business_id
    assert created_event["payload"]["provider_key"] == created.provider_key
    assert created_event["payload"]["provider_version"] == 1
    assert "metadata" not in created_event["payload"]
    assert "secret_fields_bound" not in created_event["payload"]

    updated = store.put(
        _status(
            connected=False,
            onboarding_ready=False,
            last_updated_utc="2026-09-16T00:00:00+00:00",
            metadata={"secret_value": "still-not-projected"},
        )
    )
    assert updated.connected is False
    updated_rows = list(
        events.iter_events(
            tenant_id=updated.tenant_id,
            start_ms=0,
            event_type=PROVIDER_UPDATED,
        )
    )
    assert len(updated_rows) == 1
    updated_event = canonical_business_event_contract(updated_rows[0])
    assert updated_event["payload"]["provider_version"] == 2
    assert updated_event["payload"]["connected"] is False


def test_provider_activation_retry_repairs_store_to_event_crash_without_version_churn(tmp_path) -> None:
    documents = FileDistributedDocumentStore(tmp_path / "documents")
    events = _FailOnceEventStore()
    store = FileProviderActivationStore(documents, event_store=events)
    status = _status()

    with pytest.raises(RuntimeError, match="simulated provider event append failure"):
        store.put(status)
    persisted = documents.get(
        collection="provider_activation_state",
        document_id="tenant-1:business-1:telegram_messaging",
    )
    assert persisted is not None
    assert persisted["version"] == 1

    repaired = store.put(_status(last_updated_utc="2026-09-16T00:00:00+00:00"))
    assert repaired.connected is True
    persisted_after = documents.get(
        collection="provider_activation_state",
        document_id="tenant-1:business-1:telegram_messaging",
    )
    assert persisted_after is not None
    assert persisted_after["version"] == 1
    rows = list(
        events.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=PROVIDER_CREATED,
        )
    )
    assert len(rows) == 1


def test_provider_activation_store_can_require_event_spine(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="PROVIDER_EVENT_STORE_REQUIRED"):
        FileProviderActivationStore(
            FileDistributedDocumentStore(tmp_path / "documents"),
            require_event_spine=True,
        )


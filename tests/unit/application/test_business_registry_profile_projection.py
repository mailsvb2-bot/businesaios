from __future__ import annotations

import pytest

from application.business_autonomy.distributed_capability_trust_registry import (
    BusinessRegistryRecord,
    DistributedBusinessRegistry,
)
from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier
from contracts.event_store import canonical_business_event_contract
from core.events.event_types import BUSINESS_CREATED, BUSINESS_UPDATED
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class MemoryDocuments:
    def __init__(self) -> None:
        self.rows = {}

    def get(self, *, collection: str, document_id: str):
        return self.rows.get((collection, document_id))

    def put(self, *, collection: str, document_id: str, payload, expected_version=None) -> int:
        current = self.rows.get((collection, document_id))
        current_version = 0 if current is None else int(current.get("version") or 0)
        if expected_version is not None and expected_version != current_version:
            raise ValueError("version mismatch")
        version = current_version + 1
        self.rows[(collection, document_id)] = {**dict(payload), "version": version}
        return version

    def list_prefix(self, *, collection: str, prefix: str, limit: int = 100):
        return [row for (name, document_id), row in self.rows.items() if name == collection and document_id.startswith(prefix)][:limit]


def test_business_profile_is_unknown_first_projection_of_canonical_registry() -> None:
    registry = DistributedBusinessRegistry(documents=MemoryDocuments())
    registry.register_or_update(
        BusinessRegistryRecord(
            business_id="business-1",
            tenant_id="tenant-1",
            ownership_key="owner-1",
            region="eu-west",
            channel_kind="api",
            capabilities=(),
            trust=BusinessTrustSnapshot(
                business_id="business-1",
                trust_tier=BusinessTrustTier.UNKNOWN,
                score=0.0,
                reasons=(),
                metadata={},
            ),
            governance_enabled=True,
            persistent_surfaces=(),
        )
    )

    profile = registry.profile_snapshot(tenant_id="tenant-1", business_id="business-1")

    assert profile.business_id == "business-1"
    assert profile.region == "eu-west"
    assert profile.name == ""
    assert profile.goal == ""

def _record(*, business_id: str = "business-1", tenant_id: str = "tenant-1", region: str = "eu-west") -> BusinessRegistryRecord:
    return BusinessRegistryRecord(
        business_id=business_id,
        tenant_id=tenant_id,
        ownership_key=f"owner:{tenant_id}:{business_id}",
        region=region,
        channel_kind="api",
        capabilities=(),
        trust=BusinessTrustSnapshot(
            business_id=business_id,
            trust_tier=BusinessTrustTier.UNKNOWN,
            score=0.0,
            reasons=(),
            metadata={},
        ),
        governance_enabled=True,
        persistent_surfaces=(),
    )


def test_business_registry_projects_create_update_and_skips_semantic_noop() -> None:
    documents = MemoryDocuments()
    events = MemoryEventStore()
    registry = DistributedBusinessRegistry(documents=documents, event_store=events)

    created = registry.register_or_update(_record())
    replay = registry.register_or_update(_record())
    updated = registry.register_or_update(_record(region="us-east"))

    assert created.version == 1
    assert replay.version == 1
    assert updated.version == 2
    created_rows = list(
        events.iter_events(tenant_id="tenant-1", start_ms=0, event_type=BUSINESS_CREATED)
    )
    updated_rows = list(
        events.iter_events(tenant_id="tenant-1", start_ms=0, event_type=BUSINESS_UPDATED)
    )
    assert len(created_rows) == 1
    assert len(updated_rows) == 1
    created_contract = canonical_business_event_contract(created_rows[0])
    updated_contract = canonical_business_event_contract(updated_rows[0])
    assert created_contract["business_id"] == "business-1"
    assert created_contract["payload"]["registry_version"] == 1
    assert updated_contract["business_id"] == "business-1"
    assert updated_contract["payload"]["registry_version"] == 2
    assert updated_contract["payload"]["region"] == "us-east"
    assert all("notes" not in item for item in created_contract["payload"]["capabilities"])
    assert "reasons" not in created_contract["payload"]["trust"]


def test_business_registry_event_spine_is_tenant_isolated() -> None:
    documents = MemoryDocuments()
    events = MemoryEventStore()
    registry = DistributedBusinessRegistry(documents=documents, event_store=events)

    registry.register_or_update(_record(business_id="shared", tenant_id="tenant-a"))
    registry.register_or_update(_record(business_id="shared", tenant_id="tenant-b"))

    tenant_a = list(
        events.iter_events(tenant_id="tenant-a", start_ms=0, event_type=BUSINESS_CREATED)
    )
    tenant_b = list(
        events.iter_events(tenant_id="tenant-b", start_ms=0, event_type=BUSINESS_CREATED)
    )
    assert len(tenant_a) == 1
    assert len(tenant_b) == 1
    assert tenant_a[0]["event_id"] != tenant_b[0]["event_id"]


class _FailOnceEventStore:
    def __init__(self) -> None:
        self.inner = MemoryEventStore()
        self.fail_once = True

    def append_event(self, event) -> None:
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("simulated event append failure")
        self.inner.append_event(event)

    def iter_events(self, **kwargs):
        return self.inner.iter_events(**kwargs)

    def count_events(self, **kwargs):
        return self.inner.count_events(**kwargs)


def test_business_registry_retry_repairs_document_to_event_crash_window_without_new_version() -> None:
    documents = MemoryDocuments()
    events = _FailOnceEventStore()
    registry = DistributedBusinessRegistry(documents=documents, event_store=events)

    with pytest.raises(RuntimeError, match="simulated event append failure"):
        registry.register_or_update(_record())

    durable = registry.get("tenant-1", "business-1")
    assert durable is not None
    assert durable.version == 1

    repaired = registry.register_or_update(_record())
    assert repaired.version == 1
    rows = list(
        events.iter_events(tenant_id="tenant-1", start_ms=0, event_type=BUSINESS_CREATED)
    )
    assert len(rows) == 1
    assert canonical_business_event_contract(rows[0])["payload"]["registry_version"] == 1


def test_business_registry_can_fail_closed_when_event_spine_is_required() -> None:
    documents = MemoryDocuments()
    with pytest.raises(RuntimeError, match="BUSINESS_EVENT_STORE_REQUIRED"):
        DistributedBusinessRegistry(
            documents=documents,
            require_event_spine=True,
        )
    assert documents.rows == {}


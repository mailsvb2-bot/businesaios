from __future__ import annotations

import pytest

from application.business_autonomy.distributed_capability_trust_registry import (
    BusinessRegistryRecord,
    DistributedBusinessRegistry,
)
from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier


class MemoryDocuments:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict] = {}

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
        return [row for (name, key), row in self.rows.items() if name == collection and key.startswith(prefix)][:limit]


def _record(*, channel_kind: str = "chatbot", adapter_key: str = "", external_ref: str = "") -> BusinessRegistryRecord:
    return BusinessRegistryRecord(
        business_id="business-1",
        tenant_id="tenant-1",
        ownership_key="owner-1",
        region="eu-west",
        channel_kind=channel_kind,
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
        channel_adapter_key=adapter_key,
        channel_external_ref=external_ref,
    )


def test_channel_identity_round_trips_through_canonical_business_registry() -> None:
    registry = DistributedBusinessRegistry(documents=MemoryDocuments())
    stored = registry.register_or_update(
        _record(adapter_key="chatbot.telegram", external_ref="telegram:42")
    )

    identity = registry.channel_identity_snapshot(tenant_id="tenant-1", business_id="business-1")

    assert stored.channel_adapter_key == "chatbot.telegram"
    assert identity.adapter_key == "chatbot.telegram"
    assert identity.external_ref == "telegram:42"
    assert identity.channel_kind.value == "chatbot"


def test_legacy_business_record_has_no_invented_channel_identity() -> None:
    registry = DistributedBusinessRegistry(documents=MemoryDocuments())
    registry.register_or_update(_record())

    with pytest.raises(KeyError, match="channel identity unavailable for legacy business record"):
        registry.channel_identity_snapshot(tenant_id="tenant-1", business_id="business-1")


def test_unrelated_registry_update_preserves_existing_channel_identity() -> None:
    registry = DistributedBusinessRegistry(documents=MemoryDocuments())
    registry.register_or_update(
        _record(adapter_key="chatbot.telegram", external_ref="telegram:42")
    )

    registry.register_or_update(_record())
    identity = registry.channel_identity_snapshot(tenant_id="tenant-1", business_id="business-1")

    assert identity.adapter_key == "chatbot.telegram"
    assert identity.external_ref == "telegram:42"


def test_channel_kind_change_requires_explicit_full_identity() -> None:
    registry = DistributedBusinessRegistry(documents=MemoryDocuments())
    registry.register_or_update(
        _record(adapter_key="chatbot.telegram", external_ref="telegram:42")
    )

    with pytest.raises(ValueError, match="channel_kind reassignment requires explicit channel identity"):
        registry.register_or_update(_record(channel_kind="website"))

from __future__ import annotations

from application.business_autonomy.distributed_capability_trust_registry import (
    BusinessRegistryRecord,
    DistributedBusinessRegistry,
)
from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier


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

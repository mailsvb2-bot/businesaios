from __future__ import annotations

from dataclasses import dataclass, field

from core.world_model.ids import new_event_id


@dataclass(frozen=True)
class WorldSnapshotRejected:
    event_id: str
    event_type: str
    snapshot_id: str
    tenant_id: str
    business_id: str
    built_at_ms: int
    reason: str
    payload: dict = field(default_factory=dict)

    @staticmethod
    def create(*, snapshot_id: str, tenant_id: str, business_id: str, built_at_ms: int, reason: str, payload: dict | None = None) -> WorldSnapshotRejected:
        return WorldSnapshotRejected(
            event_id=new_event_id("world_snapshot_rejected"),
            event_type="world_snapshot_rejected@v1",
            snapshot_id=str(snapshot_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            built_at_ms=int(built_at_ms),
            reason=str(reason),
            payload=dict(payload or {}),
        )

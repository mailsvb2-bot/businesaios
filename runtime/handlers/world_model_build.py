from __future__ import annotations

from runtime.world_model import WorldSnapshot, WorldSnapshotBuilderPort, WorldSnapshotRequest

CANON_THIN_HANDLER = True

def handle_world_model_build(builder: WorldSnapshotBuilderPort, tenant_id: str, correlation_id: str) -> WorldSnapshot:
    request = WorldSnapshotRequest(tenant_id=tenant_id, correlation_id=correlation_id)
    return builder.build(request)

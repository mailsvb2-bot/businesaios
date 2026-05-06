from __future__ import annotations


CANON_WORLD_SNAPSHOT_SERVICE_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True


from runtime.world_model import InMemorySnapshotRepository, WorldModelService


def build_world_snapshot_service() -> WorldModelService:
    return WorldModelService(repository=InMemorySnapshotRepository())

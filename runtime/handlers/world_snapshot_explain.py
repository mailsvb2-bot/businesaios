from __future__ import annotations

from runtime.world_model import WorldSnapshot, WorldSnapshotExplainer

CANON_THIN_HANDLER = True

def handle_world_snapshot_explain(snapshot: WorldSnapshot) -> dict:
    return WorldSnapshotExplainer().explain(snapshot=snapshot)

from __future__ import annotations

CANON_THIN_HANDLER = True

from runtime.world_model import WorldSnapshot, WorldSnapshotExplainer


def handle_world_snapshot_explain(snapshot: WorldSnapshot) -> dict:
    return WorldSnapshotExplainer().explain(snapshot=snapshot)

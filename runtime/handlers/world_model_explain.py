from __future__ import annotations

from runtime.world_model import WorldSnapshot, explain_world_snapshot

CANON_THIN_HANDLER = True

def handle_world_model_explain(snapshot: WorldSnapshot) -> str:
    return explain_world_snapshot(snapshot)

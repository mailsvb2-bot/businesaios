from __future__ import annotations

CANON_THIN_HANDLER = True
from runtime.world_model import WorldSnapshot, explain_world_snapshot


def handle_world_model_explain(snapshot: WorldSnapshot) -> str:
    return explain_world_snapshot(snapshot)

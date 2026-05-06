from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from core.behavior.builders.behavioral_state_builder import build_behavioral_state
from core.behavior.runtime.soft_backoff_preset import apply_soft_backoff_preset
from core.behavior.runtime.world_state_behavior_merger import merge_behavior_payload_into_world_state


def build_world_state_with_behavior(
    entity_id: str,
    events: list[Mapping[str, Any]],
    world_state: dict[str, object],
    *,
    catalog_root: Path,
    policy_root: Path,
) -> dict[str, object]:
    behavior_state = build_behavioral_state(
        entity_id,
        events,
        catalog_root=catalog_root,
        policy_root=policy_root,
    )
    merged = merge_behavior_payload_into_world_state(world_state, behavior_state["payload"])
    return apply_soft_backoff_preset(merged)

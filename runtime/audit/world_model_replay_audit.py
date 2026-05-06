from __future__ import annotations

from typing import Any, Dict

from runtime.world_model import extract_pinned_world_model_meta_from_payload
from runtime.world_model import replay_state_against_world_model
from runtime.enforcement.world_model_pin_guard import check_world_model_pin


def audit_decision_against_current_world_model(
    *,
    decision_payload: Dict[str, Any],
    state: Any,
    world_model: Any | None,
) -> Dict[str, Any]:
    pinned = extract_pinned_world_model_meta_from_payload(decision_payload)
    replay = replay_state_against_world_model(
        state=state,
        world_model=world_model,
    )
    pin_check = check_world_model_pin(
        pinned_meta=pinned,
        state=state,
    )

    return {
        "pinned_world_model_meta": dict(pinned),
        "pin_check": pin_check.to_dict(),
        "replay": replay,
    }

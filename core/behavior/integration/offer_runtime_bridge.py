from __future__ import annotations

def merge_behavior_offer_constraints(world_state: dict[str, object], behavior_payload: dict[str, object]) -> dict[str, object]:
    result = dict(world_state)
    result.setdefault("offer_constraints", {})
    result["offer_constraints"] = {
        **dict(result["offer_constraints"]),
        **dict(behavior_payload.get("offer_constraints", {})),
    }
    return result

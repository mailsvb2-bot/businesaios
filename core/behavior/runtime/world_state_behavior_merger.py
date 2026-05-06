from __future__ import annotations

from core.behavior.guards.decision_rights import assert_behavior_payload_is_non_executable
from core.behavior.integration.offer_runtime_bridge import merge_behavior_offer_constraints
from core.behavior.integration.pricing_runtime_bridge import merge_behavior_price_constraints


def merge_behavior_payload_into_world_state(world_state: dict[str, object], behavior_payload: dict[str, object]) -> dict[str, object]:
    assert_behavior_payload_is_non_executable(behavior_payload)
    result = dict(world_state)
    result = merge_behavior_price_constraints(result, behavior_payload)
    result = merge_behavior_offer_constraints(result, behavior_payload)
    result.setdefault("behavior", {})
    result["behavior"] = {
        **dict(result["behavior"]),
        **dict(behavior_payload.get("behavior", {})),
    }
    result.setdefault("contact_constraints", {})
    result["contact_constraints"] = {
        **dict(result["contact_constraints"]),
        **dict(behavior_payload.get("contact_constraints", {})),
    }
    return result

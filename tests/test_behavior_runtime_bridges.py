from __future__ import annotations

from core.behavior.integration.offer_runtime_bridge import merge_behavior_offer_constraints
from core.behavior.integration.pricing_runtime_bridge import merge_behavior_price_constraints


def test_merge_behavior_price_constraints_chooses_more_conservative_band() -> None:
    world_state = {"price_constraints": {"max_band": "standard"}}
    behavior_payload = {"price_constraints": {"max_band": "low", "mode": "safe"}}
    result = merge_behavior_price_constraints(world_state, behavior_payload)
    assert result["price_constraints"]["max_band"] == "low"
    assert result["price_constraints"]["mode"] == "safe"


def test_merge_behavior_offer_constraints_overlays_behavior() -> None:
    world_state = {"offer_constraints": {"aggressive_allowed": True}}
    behavior_payload = {"offer_constraints": {"aggressive_allowed": False}}
    result = merge_behavior_offer_constraints(world_state, behavior_payload)
    assert result["offer_constraints"]["aggressive_allowed"] is False

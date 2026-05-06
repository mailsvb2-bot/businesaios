from __future__ import annotations

from core.behavior.integration.offer_selection_guard import (
    filter_candidates_by_behavior_constraints,
)
from core.behavior.integration.pricing_offer_join import (
    apply_behavior_to_offer_price_candidate,
)


def test_filter_candidates_by_behavior_constraints_removes_disallowed_items() -> None:
    candidates = [
        {"offer_id": "offer_90_a", "aggressive": False, "placement": "normal"},
        {"offer_id": "offer_x", "aggressive": True, "placement": "normal"},
        {"offer_id": "offer_y", "aggressive": False, "placement": "normal"},
    ]
    result = filter_candidates_by_behavior_constraints(
        candidates,
        {
            "disallow_offer_prefixes": ("offer_90",),
            "aggressive_allowed": False,
            "paywall_first_allowed": True,
        },
    )
    assert [item["offer_id"] for item in result] == ["offer_y"]


def test_apply_behavior_to_offer_price_candidate_caps_band() -> None:
    result = apply_behavior_to_offer_price_candidate(
        {"band": "premium", "pricing_mode": "normal"},
        {"max_band": "low", "mode": "safe", "premium_allowed": False},
    )
    assert result["band"] == "low"
    assert result["pricing_mode"] == "safe"

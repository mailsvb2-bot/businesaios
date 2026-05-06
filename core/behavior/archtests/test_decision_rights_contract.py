from __future__ import annotations

import pytest

from core.behavior.guards.decision_rights import assert_behavior_payload_is_non_executable


def test_behavior_payload_accepts_readonly_contract() -> None:
    assert_behavior_payload_is_non_executable(
        {
            "behavior": {"coherence_score": 0.8},
            "price_constraints": {"max_band": "low"},
            "offer_constraints": {"aggressive_allowed": False},
            "contact_constraints": {"retry_cooldown_level": 1},
        }
    )


def test_behavior_payload_rejects_executable_decisions() -> None:
    with pytest.raises(ValueError):
        assert_behavior_payload_is_non_executable(
            {
                "behavior": {},
                "selected_offer": "offer_x",
            }
        )

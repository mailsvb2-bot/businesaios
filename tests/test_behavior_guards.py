from __future__ import annotations

import pytest

from core.behavior.guards.decision_rights import assert_behavior_payload_is_non_executable
from core.behavior.guards.no_hidden_selection import assert_no_hidden_selection


def test_behavior_payload_is_non_executable_accepts_constraints_only() -> None:
    payload = {
        "behavior": {},
        "price_constraints": {},
        "offer_constraints": {},
        "contact_constraints": {},
    }
    assert_behavior_payload_is_non_executable(payload)


def test_behavior_payload_rejects_actions() -> None:
    with pytest.raises(ValueError):
        assert_behavior_payload_is_non_executable({"behavior": {}, "actions": ["sell"]})


def test_no_hidden_selection_rejects_winner_keys() -> None:
    with pytest.raises(ValueError):
        assert_no_hidden_selection({"winning_offer_id": 1.0})

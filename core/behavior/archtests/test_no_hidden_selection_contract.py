from __future__ import annotations

import pytest

from core.behavior.guards.no_hidden_selection import assert_no_hidden_selection


def test_no_hidden_selection_accepts_observables_only() -> None:
    assert_no_hidden_selection(
        {
            "coherence_score": 0.7,
            "anti_field_level": 0.2,
        }
    )


def test_no_hidden_selection_rejects_decision_like_keys() -> None:
    with pytest.raises(ValueError):
        assert_no_hidden_selection(
            {
                "winning_offer_id": 0.9,
            }
        )

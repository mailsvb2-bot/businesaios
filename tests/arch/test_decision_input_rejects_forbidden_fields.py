from __future__ import annotations

from canon.decision_input_rules import assert_safe_recommendations


def test_decision_input_rules_accept_safe_recommendation() -> None:
    assert_safe_recommendations(
        (
            {
                "kind": "autonomy_advisory",
                "phase": "scale",
                "expected_value_score": 0.4,
            },
        )
    )


def test_decision_input_rules_reject_winner_field() -> None:
    try:
        assert_safe_recommendations(
            (
                {
                    "winner": "creative_1",
                },
            )
        )
    except RuntimeError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")

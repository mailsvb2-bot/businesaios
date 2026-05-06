from __future__ import annotations

from canon.behavioral_model_boundaries import assert_model_boundary


def test_behavioral_model_boundary_guard_accepts_safe_api() -> None:
    assert_model_boundary(
        (
            "inspect",
            "observe",
            "snapshot",
            "score",
            "forecast",
            "recommendations",
            "build_packet",
        )
    )


def test_behavioral_model_boundary_guard_rejects_decision_api() -> None:
    try:
        assert_model_boundary(
            (
                "inspect",
                "launch_campaign",
                "reallocate_budget",
            )
        )
    except RuntimeError as exc:
        assert "second brain" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")

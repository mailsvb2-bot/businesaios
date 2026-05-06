from __future__ import annotations

from canon.behavioral_model_boundaries import assert_model_boundary


def test_history_and_segment_layers_are_not_decision_engines() -> None:
    assert_model_boundary(
        (
            "record",
            "inspect",
            "build_packet",
            "read_packet",
            "append",
        )
    )

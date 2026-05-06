from __future__ import annotations

from ml.common.confidence import Confidence
from ml.common.score_output import ScoreOutput


def test_confidence_bounded_handles_nan() -> None:
    assert Confidence(float('nan')).bounded() == 0.0


def test_score_output_bounded_score_clamps_and_sanitizes() -> None:
    output = ScoreOutput(score=float('inf'), confidence=float('nan'))
    assert output.bounded_score() == 0.0
    assert output.bounded_confidence() == 0.0

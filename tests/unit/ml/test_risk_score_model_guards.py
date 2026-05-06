from __future__ import annotations

from ml.scoring.risk_score_model import RiskScoreModel


def test_risk_score_model_ignores_bad_numeric_inputs() -> None:
    output = RiskScoreModel().score({'volatility': 'bad', 'risk_flags': None, 'budget_delta': float('inf')})
    assert output.score == 0.0
    assert output.confidence == 0.8

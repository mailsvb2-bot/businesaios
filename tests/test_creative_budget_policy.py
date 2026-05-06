from __future__ import annotations

from core.creative_intelligence.budget_policy import build_budget_advice
from core.creative_intelligence.models import (
    CreativeIntelligenceSnapshot,
    CreativePnLSnapshot,
    ExperimentConfidenceSnapshot,
    IncrementalitySnapshot,
)


def test_budget_policy_returns_ordered_ranges() -> None:
    advice = build_budget_advice(
        snapshot=CreativeIntelligenceSnapshot(
            creative_id="c1",
            pnl=CreativePnLSnapshot("c1", 400.0, 200.0, 200.0, 0.50, 1.0),
            incrementality=IncrementalitySnapshot("c1", 0.12, 0.70, 0.20, "dr"),
            experiment_confidence=ExperimentConfidenceSnapshot("c1", 0.15, 0.04, 0.96, 0.80),
            expected_value_score=0.42,
            downside_envelope=0.20,
            portfolio_rank_score=0.50,
            explanations=(),
        ),
        total_budget=10000.0,
    )
    assert advice.floor_budget <= advice.target_budget <= advice.ceiling_budget

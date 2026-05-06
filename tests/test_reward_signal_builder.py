from __future__ import annotations

from core.creative_intelligence.models import (
    CreativeIntelligenceSnapshot,
    CreativePnLSnapshot,
    ExperimentConfidenceSnapshot,
    IncrementalitySnapshot,
)
from core.reward_bridge.reward_signal_builder import build_reward_signal


def test_reward_signal_builder_returns_scalarized_signal() -> None:
    signal = build_reward_signal(
        snapshot=CreativeIntelligenceSnapshot(
            creative_id="c1",
            pnl=CreativePnLSnapshot("c1", 400.0, 200.0, 200.0, 0.5, 1.0),
            incrementality=IncrementalitySnapshot("c1", 0.15, 0.8, 0.2, "dr"),
            experiment_confidence=ExperimentConfidenceSnapshot("c1", 0.12, 0.03, 0.97, 0.85),
            expected_value_score=0.35,
            downside_envelope=0.25,
            portfolio_rank_score=0.4,
            explanations=(),
        ),
        architecture_global_stability=0.8,
        blast_radius_risk=0.2,
        flow_turbulence=0.1,
        market_competitive_shift=0.3,
    )
    assert signal.scalarized_value() > -1.0

from __future__ import annotations

from core.creative_intelligence.models import CreativeEconomicsInput, CreativeEvidenceBundle
from core.creative_intelligence.snapshot_builder import build_creative_snapshot
from core.experiments.enums import RiskLevel, RolloutDecision
from core.experiments.types import EvaluationSummary


def test_creative_snapshot_builds_positive_signal() -> None:
    snapshot = build_creative_snapshot(
        item=CreativeEconomicsInput(
            creative_id="c1",
            segment_key="seg_a",
            spend=100.0,
            impressions=10000,
            clicks=300,
            conversions=20,
            revenue=500.0,
            cogs=80.0,
            variable_cost=20.0,
            fixed_cost_share=10.0,
            attribution_credit=0.8,
            expected_future_value=0.4,
            market_fit_score=0.7,
        ),
        evidence=CreativeEvidenceBundle(
            experiment_summary=EvaluationSummary(
                experiment_id="exp1",
                significant=True,
                uplift=0.18,
                p_value=0.03,
                risk_level=RiskLevel.LOW,
                rollout_decision=RolloutDecision.FULL,
                reasons=[],
            )
        ),
    )
    assert snapshot.pnl.attributed_revenue > 0.0
    assert snapshot.expected_value_score != 0.0

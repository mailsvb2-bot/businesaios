from __future__ import annotations

from core.reward.reward_details import build_reward_details
from core.growth.ads.rl.off_policy import OpeEstimate, OffPolicyActionScore
from learning.trainer import build_validation_score_view


def test_reward_details_builder() -> None:
    details = build_reward_details(reward=1.5, ltv=2.0, spend=0.5)
    assert details.reward == 1.5
    assert details.source == "advisory_reward_details"


def test_validation_score_view_builder() -> None:
    out = build_validation_score_view(avg_reward=1.2, baseline_drop=0.1)
    assert len(out) == 2
    assert out[0].metric_name == "avg_reward"

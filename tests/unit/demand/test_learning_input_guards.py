from __future__ import annotations

from demand_learning.business_quality_learning_loop import BusinessQualityLearningLoop
from demand_learning.policy_promotion import PolicyPromotion
from demand_learning.policy_rollback import PolicyRollback
from demand_learning.policy_state import PolicyState
from demand_learning.revenue_outcome_learning_loop import RevenueOutcomeLearningLoop


def test_policy_rollback_handles_bad_metric_payloads() -> None:
    assert PolicyRollback().allow({'sample_size': 'bad', 'offline_conversion_rate': None, 'offline_bad_outcome_rate': object()}) is False


def test_policy_promotion_handles_bad_metric_payloads() -> None:
    assert PolicyPromotion().allow({'sample_size': 'bad', 'offline_conversion_rate': float('nan')}) is False


def test_revenue_outcome_learning_loop_ignores_bad_revenue_values() -> None:
    result = RevenueOutcomeLearningLoop().propose_revenue_updates(({'revenue': 'bad'}, {'revenue': -10}, {'revenue': 12.5}))
    assert result['total_revenue'] == 12.5


def test_business_quality_learning_loop_clamps_bad_scores() -> None:
    result = BusinessQualityLearningLoop().propose_quality_updates(({'quality_score': 'bad'}, {'quality_score': 2.0}, {'quality_score': 0.5}))
    assert result['quality_mean'] == (0.0 + 1.0 + 0.5) / 3


def test_policy_state_adjustment_is_safe_on_bad_values() -> None:
    state = PolicyState(fairness_boost={'biz-1': 'bad'}, causal_bonus={'biz-1': float('inf')}, risk_penalty={'biz-1': 0.25})
    assert state.adjustment_for('biz-1') == -0.25

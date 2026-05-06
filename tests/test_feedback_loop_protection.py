import time

import pytest

from learning.replay import (
    FeedbackLoopFirewall,
    FeedbackLoopViolation,
    PolicyMetadata,
)
from ml.datasets.policy_dataset_splitter import PolicyDatasetSplitter
from ml.evaluation.policy_evaluator import EvaluationSample, PolicyEvaluator
from ml.policy_promotion_guard import EvaluationSnapshot, PolicyPromotionGuard, PromotionBlocked
from ml.policy_rollout_manager import PolicyRolloutManager, RolloutGuardViolation
from runtime.autopilot_feedback_guard import AutopilotFeedbackGuard, AutopilotFeedbackGuardViolation


class _Policy:
    def act(self, state):
        return state * 2


class _Sample(EvaluationSample):
    def __init__(self, state):
        super().__init__(state=state, reward_function=self._reward)

    def _reward(self, action):
        return 1.0 if action >= self.state else 0.0


def test_train_eval_dataset_must_differ():
    firewall = FeedbackLoopFirewall()
    with pytest.raises(FeedbackLoopViolation):
        firewall.validate_dataset_separation(train_dataset_id="dataset_1", eval_dataset_id="dataset_1")


def test_policy_cannot_be_evaluated_on_training_dataset():
    firewall = FeedbackLoopFirewall()
    policy = PolicyMetadata(policy_id="p1", trained_at_ms=0, source_dataset_id="train_1", evaluation_dataset_id=None)
    with pytest.raises(FeedbackLoopViolation):
        firewall.validate_policy_eval_dataset(policy, eval_dataset_id="train_1")


def test_policy_eval_delay_is_enforced():
    firewall = FeedbackLoopFirewall()
    policy = PolicyMetadata(
        policy_id="p1",
        trained_at_ms=int(time.time() * 1000),
        source_dataset_id="train_1",
        evaluation_dataset_id="eval_1",
    )
    with pytest.raises(FeedbackLoopViolation):
        firewall.validate_eval_delay(policy)


def test_rollout_manager_requires_distinct_baseline_and_candidate():
    manager = PolicyRolloutManager()
    with pytest.raises(RolloutGuardViolation):
        manager.start_rollout("r1", baseline_policy="p1", candidate_policy="p1", traffic_fraction=0.1)


def test_rollout_promotion_waits_for_soak_period():
    manager = PolicyRolloutManager()
    manager.start_rollout("r1", baseline_policy="base", candidate_policy="cand", traffic_fraction=0.1)
    with pytest.raises(RolloutGuardViolation):
        manager.promote("r1")


def test_promotion_guard_requires_improvement_and_sample_size():
    guard = PolicyPromotionGuard()
    baseline = EvaluationSnapshot(policy_id="base", mean_reward=0.50, reward_std=0.1, samples=1000)
    weak = EvaluationSnapshot(policy_id="cand", mean_reward=0.51, reward_std=0.1, samples=100)
    with pytest.raises(PromotionBlocked):
        guard.require_allowed(baseline, weak)


def test_dataset_splitter_creates_non_empty_train_and_eval():
    splitter = PolicyDatasetSplitter()
    result = splitter.split(list(range(10)), eval_fraction=0.2)
    assert result.train
    assert result.evaluation
    assert len(result.train) + len(result.evaluation) == 10


def test_policy_evaluator_is_independent_and_returns_metrics():
    evaluator = PolicyEvaluator()
    result = evaluator.evaluate("p1", _Policy(), [_Sample(1), _Sample(2), _Sample(3)])
    assert result.samples == 3
    assert result.mean_reward >= 0.0
    assert result.reward_std >= 0.0


def test_autopilot_feedback_guard_blocks_same_origin():
    guard = AutopilotFeedbackGuard()
    with pytest.raises(AutopilotFeedbackGuardViolation):
        guard.validate_action_vs_evaluation("ai_autopilot", "ai_autopilot")

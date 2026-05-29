from __future__ import annotations

"""Canonical offline evaluation surface with compat alias submodules."""

from runtime.platform.support.contracts.evaluation import EvaluationResult


def _doubly_robust(
    rewards: list[float],
    ratios: list[float],
    q_values: list[float],
    v_values: list[float],
) -> float:
    if not rewards:
        return 0.0
    total = 0.0
    for reward, ratio, q_value, v_value in zip(rewards, ratios, q_values, v_values, strict=False):
        total += v_value + ratio * (reward - q_value)
    return total / len(rewards)

class FittedQEvaluation:
    def estimate(self, q_values: list[float]) -> float:
        if not q_values:
            return 0.0
        return sum(q_values) / len(q_values)

def _importance_sampling(rewards: list[float], ratios: list[float]) -> float:
    if not rewards:
        return 0.0
    weighted = [reward * ratio for reward, ratio in zip(rewards, ratios, strict=False)]
    return sum(weighted) / len(weighted)

def _weighted_importance_sampling(rewards: list[float], ratios: list[float]) -> float:
    denominator = sum(ratios)
    if denominator == 0:
        return 0.0
    numerator = sum(reward * ratio for reward, ratio in zip(rewards, ratios, strict=False))
    return numerator / denominator

class OffPolicyEvaluation:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        rewards = list(payload.get("rewards", []))
        ratios = list(payload.get("ratios", []))
        estimate = _weighted_importance_sampling(rewards=rewards, ratios=ratios)
        return EvaluationResult(candidate_id=candidate_id, metrics={"wis": estimate})

class OfflineEvaluator:
    def __init__(self, ope: OffPolicyEvaluation | None = None) -> None:
        self._ope = ope or OffPolicyEvaluation()

    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        return self._ope.evaluate(candidate_id, payload)

def _regression_delta(previous: float, current: float) -> float:
    return current - previous

class ReplayBasedEval:
    def estimate(self, replay_samples) -> float:
        rewards = [sample.reward.value for sample in replay_samples]
        if not rewards:
            return 0.0
        return sum(rewards) / len(rewards)

_MODULE_EXPORTS = {
    "doubly_robust": {"doubly_robust": f"{__name__}:_doubly_robust"},
    "fitted_q_evaluation": {"FittedQEvaluation": f"{__name__}:FittedQEvaluation"},
    "importance_sampling": {"importance_sampling": f"{__name__}:_importance_sampling"},
    "off_policy_evaluation": {"OffPolicyEvaluation": f"{__name__}:OffPolicyEvaluation"},
    "offline_evaluator": {"OfflineEvaluator": f"{__name__}:OfflineEvaluator"},
    "offline_regression_checks": {"regression_delta": f"{__name__}:_regression_delta"},
    "replay_based_eval": {"ReplayBasedEval": f"{__name__}:ReplayBasedEval"},
    "weighted_importance_sampling": {"weighted_importance_sampling": f"{__name__}:_weighted_importance_sampling"},
}

__all__ = [
    "FittedQEvaluation",
    "OffPolicyEvaluation",
    "OfflineEvaluator",
    "ReplayBasedEval",
] + list(_MODULE_EXPORTS)

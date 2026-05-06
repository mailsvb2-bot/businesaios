from __future__ import annotations

"""Canonical online evaluation surface with compat alias submodules."""

from runtime.platform.support.contracts.evaluation import EvaluationResult

class CanaryEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = float(payload.get("canary_score", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"canary_score": score})

class HoldoutEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = float(payload.get("holdout_score", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"holdout_score": score})

class LiveRewardTracking:
    def track(self, rewards: list[float]) -> float:
        if not rewards:
            return 0.0
        return sum(rewards) / len(rewards)

class LiveSafetyEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        violations = float(payload.get("violations", 0.0))
        safety = max(0.0, 1.0 - violations)
        return EvaluationResult(candidate_id=candidate_id, metrics={"live_safety": safety})

class ShadowEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = float(payload.get("shadow_score", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"shadow_score": score})

class StagedRolloutEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = float(payload.get("staged_score", 0.0))
        return EvaluationResult(candidate_id=candidate_id, metrics={"staged_score": score})

class OnlineEvaluator:
    def __init__(self, canary: CanaryEval | None = None, shadow: ShadowEval | None = None) -> None:
        self._canary = canary or CanaryEval()
        self._shadow = shadow or ShadowEval()

    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        canary_result = self._canary.evaluate(candidate_id, payload)
        shadow_result = self._shadow.evaluate(candidate_id, payload)
        score = (
            canary_result.metrics.get("canary_score", 0.0)
            + shadow_result.metrics.get("shadow_score", 0.0)
        ) / 2.0
        return EvaluationResult(candidate_id=candidate_id, metrics={"online_score": score})

_ALIAS_EXPORTS = {
    "canary_eval": "CanaryEval",
    "holdout_eval": "HoldoutEval",
    "live_reward_tracking": "LiveRewardTracking",
    "live_safety_eval": "LiveSafetyEval",
    "online_evaluator": "OnlineEvaluator",
    "shadow_eval": "ShadowEval",
    "staged_rollout_eval": "StagedRolloutEval",
}

__all__ = [
    "CanaryEval",
    "HoldoutEval",
    "LiveRewardTracking",
    "LiveSafetyEval",
    "OnlineEvaluator",
    "ShadowEval",
    "StagedRolloutEval",
] + list(_ALIAS_EXPORTS)

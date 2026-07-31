from __future__ import annotations
from runtime.platform.support.contracts.evaluation import EvaluationResult
class CanaryEval:
    def evaluate(self, candidate_id, payload): return EvaluationResult(candidate_id=candidate_id, metrics={"canary_score": float(payload.get("canary_score", 0.0))})
class HoldoutEval:
    def evaluate(self, candidate_id, payload): return EvaluationResult(candidate_id=candidate_id, metrics={"holdout_score": float(payload.get("holdout_score", 0.0))})
class LiveRewardTracking:
    def track(self, rewards): return sum(rewards) / len(rewards) if rewards else 0.0
class LiveSafetyEval:
    def evaluate(self, candidate_id, payload): return EvaluationResult(candidate_id=candidate_id, metrics={"live_safety": max(0.0, 1.0 - float(payload.get("violations", 0.0)))})
class ShadowEval:
    def evaluate(self, candidate_id, payload): return EvaluationResult(candidate_id=candidate_id, metrics={"shadow_score": float(payload.get("shadow_score", 0.0))})
class StagedRolloutEval:
    def evaluate(self, candidate_id, payload): return EvaluationResult(candidate_id=candidate_id, metrics={"staged_score": float(payload.get("staged_score", 0.0))})
class OnlineEvaluator:
    def __init__(self, canary=None, shadow=None): self._canary, self._shadow = canary or CanaryEval(), shadow or ShadowEval()
    def evaluate(self, candidate_id, payload):
        score = self._canary.evaluate(candidate_id, payload).metrics.get("canary_score", 0.0) + self._shadow.evaluate(candidate_id, payload).metrics.get("shadow_score", 0.0)
        return EvaluationResult(candidate_id=candidate_id, metrics={"online_score": score / 2.0})
_ALIAS_EXPORTS = {"canary_eval":"CanaryEval", "holdout_eval":"HoldoutEval", "live_reward_tracking":"LiveRewardTracking", "live_safety_eval":"LiveSafetyEval", "online_evaluator":"OnlineEvaluator", "shadow_eval":"ShadowEval", "staged_rollout_eval":"StagedRolloutEval"}
__all__ = list(_ALIAS_EXPORTS.values()) + list(_ALIAS_EXPORTS)

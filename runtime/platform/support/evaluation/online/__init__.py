from __future__ import annotations
from dataclasses import dataclass
from core.policies.shadow import ShadowEvaluator as ShadowEval
from core.policies.staged_rollout import RolloutGuard as StagedRolloutEval
@dataclass(frozen=True)
class EvaluationResult:
    candidate_id: str
    metrics: dict[str, float]

class CanaryEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        return EvaluationResult(candidate_id, {"canary_score": float(payload.get("canary_score", 0.0))})


class LiveEval:
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        return EvaluationResult(candidate_id, {"live_safety": max(0.0, 1.0 - float(payload.get("violations", 0.0)))})


class OnlineEvaluator:
    def __init__(self, canary: CanaryEval | None = None, shadow: object | None = None) -> None: self._canary, self._shadow = canary or CanaryEval(), shadow
    def evaluate(self, candidate_id: str, payload) -> EvaluationResult:
        score = self._canary.evaluate(candidate_id, payload).metrics["canary_score"]
        return EvaluationResult(candidate_id, {"online_score": (score + float(payload.get("shadow_score", 0.0))) / 2.0})


__all__ = ["CanaryEval", "EvaluationResult", "LiveEval", "OnlineEvaluator", "ShadowEval", "StagedRolloutEval"]

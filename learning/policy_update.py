from __future__ import annotations

from dataclasses import dataclass

from shared.numbers import coerce_float
from shared.result import Result


class PromotionBlocked(Exception):
    """Raised when candidate policy promotion is not allowed."""


@dataclass(frozen=True)
class PromotionDecision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class EvaluationSnapshot:
    policy_id: str
    mean_reward: float
    reward_std: float
    samples: int

    @property
    def reward_mean(self) -> float:
        return self.mean_reward


EvaluationResult = EvaluationSnapshot


class PolicyPromotionGuard:
    def __init__(self, min_sample_size: int = 500, min_improvement: float = 0.03) -> None:
        self._min_sample_size = min_sample_size
        self._min_improvement = min_improvement

    def assess_promotion(self, baseline: EvaluationSnapshot, candidate: EvaluationSnapshot) -> PromotionDecision:
        if baseline.policy_id == candidate.policy_id:
            return PromotionDecision(False, "Candidate policy must differ from baseline policy.")
        if candidate.samples < self._min_sample_size:
            return PromotionDecision(False, f"Candidate sample size is too small: {candidate.samples} < {self._min_sample_size}.")
        improvement = candidate.mean_reward - baseline.mean_reward
        if improvement < self._min_improvement:
            return PromotionDecision(False, f"Candidate improvement is insufficient: {improvement:.6f} < {self._min_improvement:.6f}.")
        return PromotionDecision(True, "Candidate policy passed promotion guard.")

    def require_allowed(self, baseline: EvaluationSnapshot, candidate: EvaluationSnapshot) -> None:
        decision = self.assess_promotion(baseline, candidate)
        if not decision.allowed:
            raise PromotionBlocked(decision.reason)

    def can_promote(self, baseline: EvaluationSnapshot, candidate: EvaluationSnapshot) -> bool:
        self.require_allowed(baseline, candidate)
        return True


class OnlineUpdate:
    def apply(self, model_name: str, observations: list[dict]) -> Result:
        normalized_name = str(model_name or "").strip()
        if not normalized_name:
            return Result.failure(code="online_update_missing_model_name", message="online update requires model_name")
        if not isinstance(observations, list):
            return Result.failure(code="online_update_observations_must_be_list", message="online update observations must be a list", model_name=normalized_name)
        if not observations:
            return Result.failure(code="online_update_observations_empty", message="online update requires at least one observation", model_name=normalized_name)
        normalized_rows: list[dict[str, object]] = []
        for item in observations:
            if not isinstance(item, dict):
                return Result.failure(code="online_update_observations_must_be_dicts", message="online update observations must be dict items", model_name=normalized_name)
            entity_id = str(item.get("entity_id") or "").strip()
            if not entity_id:
                return Result.failure(code="online_update_missing_entity_id", message="each observation must include entity_id", model_name=normalized_name)
            label = coerce_float(item.get("label", item.get("outcome", 0.0)), 0.0, minimum=0.0, maximum=1.0)
            weight = coerce_float(item.get("weight", 1.0), 1.0, minimum=0.0, maximum=100.0)
            normalized_rows.append({"entity_id": entity_id, "label": label, "weight": weight})
        return Result.success(code="online_update_buffered", model_name=normalized_name, count=len(normalized_rows), observations=normalized_rows)

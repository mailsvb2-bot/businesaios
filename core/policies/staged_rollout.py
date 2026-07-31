from __future__ import annotations
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol
from config.staged_rollout_policy import DEFAULT_STAGED_ROLLOUT_POLICY, StagedRolloutPolicy
class RolloutStage(str, Enum):
    OFFLINE, SHADOW, PROD = "offline", "shadow", "prod"

class ShadowRunner(Protocol):
    def run(self, policy: Any, live_stream: Iterable[dict[str, Any]]) -> dict[str, Any]: ...


class RolloutGuard:
    @staticmethod
    def allow_promotion(m: dict[str, Any], *, policy: StagedRolloutPolicy = DEFAULT_STAGED_ROLLOUT_POLICY) -> bool:
        try:
            return all((int(m.get("decision_count", 0)) >= policy.min_shadow_decisions,
                int(m.get("production_outcome_count", 0)) >= policy.min_production_outcomes,
                int(m.get("outcome_count", 0)) >= policy.min_outcome_observations,
                float(m.get("error_rate", policy.fallback_error_rate)) <= policy.max_error_rate_for_promotion,
                float(m.get("disagreement_rate", 1.0)) <= policy.max_disagreement_rate,
                int(m.get("critical_violations", 1)) <= policy.max_critical_violations,
                float(m.get("average_cost_increase", float("inf"))) <= policy.max_average_cost_increase,
                float(m.get("average_regret", float("inf"))) <= policy.max_average_regret,
                float(m.get("p95_latency_ms", float("inf"))) <= policy.max_p95_latency_ms))
        except (TypeError, ValueError): return False


@dataclass(frozen=True)
class StagedRollout:
    shadow: ShadowRunner
    rollout_policy: StagedRolloutPolicy = DEFAULT_STAGED_ROLLOUT_POLICY

    def evaluate(self, *, has_offline_candidate: bool, policy: Any, live_stream: Iterable[dict[str, Any]]) -> RolloutStage:
        if not has_offline_candidate: return RolloutStage.OFFLINE
        return RolloutStage.PROD if RolloutGuard.allow_promotion(self.shadow.run(policy, live_stream), policy=self.rollout_policy) else RolloutStage.SHADOW

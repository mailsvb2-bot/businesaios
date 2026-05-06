from __future__ import annotations

"""V13 staged rollout pipeline (OFFLINE -> SHADOW -> PROD).

This module is intentionally minimal and deterministic.

It does NOT execute deployments. It only evaluates readiness stages.
Deployment remains a DecisionCore decision (deploy_policy/rollback_policy)
and must pass RuntimeGuard + DecisionLedger + RuntimeExecutor.
"""

from dataclasses import dataclass

from config.staged_rollout_policy import DEFAULT_STAGED_ROLLOUT_POLICY, StagedRolloutPolicy
from enum import Enum
from typing import Any, Dict, Iterable, Protocol


class RolloutStage(str, Enum):
    OFFLINE = "offline"
    SHADOW = "shadow"
    PROD = "prod"


class ShadowRunner(Protocol):
    def run(self, policy: Any, live_stream: Iterable[Dict[str, Any]]) -> Dict[str, Any]: ...


class RolloutGuard:
    """Promotion guard.

    By default, promotion is allowed if error_rate is <= policy.max_error_rate_for_promotion.
    """

    @staticmethod
    def allow_promotion(
        metrics: Dict[str, Any],
        *,
        policy: StagedRolloutPolicy = DEFAULT_STAGED_ROLLOUT_POLICY,
    ) -> bool:
        try:
            er = float(metrics.get("error_rate", float(policy.default_error_rate)))
        except Exception:
            er = float(policy.fallback_error_rate)
        return er <= float(policy.max_error_rate_for_promotion)


@dataclass(frozen=True)
class StagedRollout:
    """Evaluates stage transitions.

    OFFLINE: not enough offline evidence
    SHADOW: shadow run evidence insufficient
    PROD: allowed for production
    """

    shadow: ShadowRunner
    rollout_policy: StagedRolloutPolicy = DEFAULT_STAGED_ROLLOUT_POLICY

    def evaluate(self, *, has_offline_candidate: bool, policy: Any, live_stream: Iterable[Dict[str, Any]]) -> RolloutStage:
        if not has_offline_candidate:
            return RolloutStage.OFFLINE

        shadow_metrics = self.shadow.run(policy, live_stream)
        if not RolloutGuard.allow_promotion(shadow_metrics, policy=self.rollout_policy):
            return RolloutStage.SHADOW

        return RolloutStage.PROD
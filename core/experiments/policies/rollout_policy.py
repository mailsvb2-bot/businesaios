from __future__ import annotations

from config.experiments_policy import (
    DEFAULT_CONSERVATIVE_ROLLOUT_POLICY_DEFAULTS,
    ConservativeRolloutPolicyDefaults,
)
from core.experiments.enums import RiskLevel, RolloutDecision


class ConservativeRolloutPolicy:
    def __init__(
        self,
        policy_defaults: ConservativeRolloutPolicyDefaults = DEFAULT_CONSERVATIVE_ROLLOUT_POLICY_DEFAULTS,
    ) -> None:
        self._policy = policy_defaults

    def evaluate(self, *, significant: bool, uplift: float, risk_level: RiskLevel) -> RolloutDecision:
        if risk_level == RiskLevel.HIGH:
            return RolloutDecision.BLOCK
        if not significant:
            return RolloutDecision.HOLD
        if uplift <= self._policy.zero_uplift_floor:
            return RolloutDecision.HOLD
        if risk_level == RiskLevel.LOW:
            return RolloutDecision.FULL
        return RolloutDecision.PARTIAL

    decide = evaluate

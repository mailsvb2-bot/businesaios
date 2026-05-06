from __future__ import annotations

from core.experiments.enums import RiskLevel, RolloutDecision
from core.experiments.errors import UnsafeRolloutViolation


class UnsafeRolloutGuard:
    def ensure_safe(self, *, decision: RolloutDecision, risk_level: RiskLevel, significant: bool) -> None:
        if decision == RolloutDecision.FULL and (risk_level == RiskLevel.HIGH or not significant):
            raise UnsafeRolloutViolation("full rollout forbidden: high risk or non-significant result")
        if decision == RolloutDecision.PARTIAL and risk_level == RiskLevel.HIGH:
            raise UnsafeRolloutViolation("partial rollout forbidden: high risk result")

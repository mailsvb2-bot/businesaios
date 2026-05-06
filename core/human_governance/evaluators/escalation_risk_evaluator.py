from __future__ import annotations

from config.risk_evaluation_policy import (
    DEFAULT_ESCALATION_RISK_POLICY,
    EscalationRiskPolicy,
)

from ..enums import RiskLevel
from ..types import ApprovalState, ReviewItem


class EscalationRiskEvaluator:
    def __init__(self, policy: EscalationRiskPolicy = DEFAULT_ESCALATION_RISK_POLICY) -> None:
        self._policy = policy

    def evaluate(self, review: ReviewItem, state: ApprovalState | None) -> float:
        score = float(self._policy.base_score_by_level.get(str(review.risk_level), 0.0))

        if state is not None and state.status == "paused":
            score += float(self._policy.paused_status_addon)

        if review.metadata.get("override_applied") is True:
            score += float(self._policy.override_applied_addon)

        return min(score, float(self._policy.score_ceiling))

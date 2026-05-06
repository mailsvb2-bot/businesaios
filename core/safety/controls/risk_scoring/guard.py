from __future__ import annotations

from config.decision_safety_policy import DEFAULT_RISK_SCORE_GUARD_POLICY, RiskScoreGuardPolicy

from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .scorer import RiskScorer


class RiskScoreGuard:
    control_name = "risk_scoring"

    def __init__(self, scorer: RiskScorer, policy: RiskScoreGuardPolicy | None = None):
        self._scorer = scorer
        self._policy = policy or DEFAULT_RISK_SCORE_GUARD_POLICY

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        score = self._scorer.score(ctx)
        if score.value >= self._policy.block_threshold:
            status = ControlStatus.BLOCK
            reason = self._policy.blocked_reason
        elif score.value >= self._policy.review_threshold:
            status = ControlStatus.REVIEW
            reason = self._policy.review_reason
        else:
            status = ControlStatus.ALLOW
            reason = self._policy.ok_reason
        return ControlDecision(control=self.control_name, status=status, reason=reason, details={"score": score.value, "reasons": list(score.reasons)})

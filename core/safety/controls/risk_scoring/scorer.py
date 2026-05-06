from __future__ import annotations

from config.decision_safety_policy import DEFAULT_RISK_SCORER_POLICY, RiskScorerPolicy

from ..action_context import SafetyActionContext
from .models import RiskScore


class RiskScorer:
    def __init__(self, policy: RiskScorerPolicy | None = None) -> None:
        self._policy = policy or DEFAULT_RISK_SCORER_POLICY

    def score(self, ctx: SafetyActionContext) -> RiskScore:
        payload = dict(ctx.payload)
        policy = self._policy
        value = policy.zero_value
        reasons: list[str] = []
        if float(payload.get("amount", policy.zero_value) or policy.zero_value) > policy.amount_threshold:
            value += policy.amount_risk_increment
            reasons.append(policy.high_financial_amount_reason)
        if int(payload.get("audience_size", policy.zero_value) or policy.zero_value) > policy.audience_size_threshold:
            value += policy.audience_risk_increment
            reasons.append(policy.large_audience_reason)
        if bool(payload.get("requires_human_review")):
            value += policy.review_flag_risk_increment
            reasons.append(policy.explicit_review_flag_reason)
        return RiskScore(value=min(value, policy.score_ceiling), reasons=tuple(reasons))

from __future__ import annotations

from dataclasses import dataclass, field

from governance.economic.action_economics_model import ActionEconomicsAssessment, ActionEconomicsIntent, ActionEconomicsSnapshot
from governance.economic.economic_policy_contract import EconomicPolicyConfig, PolicyCheckResult

CANON_NON_DECISION_MODULE = True


@dataclass(frozen=True)
class SpendCapPolicy:
    config: EconomicPolicyConfig = field(default_factory=EconomicPolicyConfig)

    def evaluate(self, *, intent: ActionEconomicsIntent, snapshot: ActionEconomicsSnapshot, assessment: ActionEconomicsAssessment) -> PolicyCheckResult:
        hard_caps: list[float] = []
        soft_caps: list[float] = []
        if snapshot.hard_spend_cap > 0.0:
            hard_caps.append(snapshot.hard_spend_cap)
        channel_cap = float(snapshot.portfolio_budgets.get(intent.channel, 0.0) or 0.0)
        if channel_cap > 0.0:
            hard_caps.append(channel_cap)
        if snapshot.planned_spend > 0.0 and self.config.use_planned_spend_as_soft_cap_only:
            soft_caps.append(snapshot.planned_spend)
        elif snapshot.planned_spend > 0.0:
            hard_caps.append(snapshot.planned_spend)
        active_hard_cap = min(hard_caps) if hard_caps else 0.0
        active_soft_cap = min(soft_caps) if soft_caps else 0.0
        if active_hard_cap > 0.0 and assessment.requested_budget > active_hard_cap:
            return PolicyCheckResult(
                policy_name="spend_cap_policy",
                status="veto",
                reason="budget_veto:spend_cap_exceeded",
                details={"requested_budget": assessment.requested_budget, "hard_cap": active_hard_cap, "soft_cap": active_soft_cap},
            )
        if active_soft_cap > 0.0:
            soft_threshold = active_soft_cap * self.config.spend_soft_cap_ratio
            if assessment.requested_budget > soft_threshold:
                return PolicyCheckResult(
                    policy_name="spend_cap_policy",
                    status="review",
                    reason="budget_review:planned_spend_soft_cap_near_limit",
                    details={"requested_budget": assessment.requested_budget, "soft_threshold": soft_threshold, "planned_spend": active_soft_cap},
                )
        return PolicyCheckResult(
            policy_name="spend_cap_policy",
            status="allow",
            reason="spend_cap_ok",
            details={"requested_budget": assessment.requested_budget, "hard_cap": active_hard_cap, "soft_cap": active_soft_cap},
        )

from __future__ import annotations

from dataclasses import dataclass, field

from governance.economic.action_economics_model import ActionEconomicsAssessment, ActionEconomicsIntent, ActionEconomicsSnapshot
from governance.economic.economic_policy_contract import EconomicPolicyConfig, PolicyCheckResult

CANON_NON_DECISION_MODULE = True


@dataclass(frozen=True)
class MarginPolicy:
    config: EconomicPolicyConfig = field(default_factory=EconomicPolicyConfig)

    def evaluate(self, *, intent: ActionEconomicsIntent, assessment: ActionEconomicsAssessment, snapshot: ActionEconomicsSnapshot) -> PolicyCheckResult:
        floor_margin = max(self.config.absolute_floor_margin, snapshot.target_margin - self.config.tolerated_margin_gap)
        min_expected_roi = max(0.0, intent.min_expected_roi)
        if assessment.expected_margin_after_action < floor_margin:
            return PolicyCheckResult(
                policy_name="margin_policy",
                status="veto",
                reason="margin_veto:below_floor",
                details={"expected_margin_after_action": assessment.expected_margin_after_action, "floor_margin": floor_margin},
            )
        if assessment.expected_roi < min_expected_roi:
            return PolicyCheckResult(
                policy_name="margin_policy",
                status="veto",
                reason="margin_veto:below_min_roi",
                details={"expected_roi": assessment.expected_roi, "min_expected_roi": min_expected_roi},
            )
        return PolicyCheckResult(
            policy_name="margin_policy",
            status="allow",
            reason="margin_ok",
            details={
                "expected_margin_after_action": assessment.expected_margin_after_action,
                "floor_margin": floor_margin,
                "expected_roi": assessment.expected_roi,
                "min_expected_roi": min_expected_roi,
            },
        )

from __future__ import annotations

from dataclasses import dataclass, field

from governance.economic.action_economics_model import ActionEconomicsAssessment
from governance.economic.economic_policy_contract import EconomicPolicyConfig, PolicyCheckResult

CANON_NON_DECISION_MODULE = True


@dataclass(frozen=True)
class RunwayProtection:
    config: EconomicPolicyConfig = field(default_factory=EconomicPolicyConfig)

    def evaluate(self, assessment: ActionEconomicsAssessment) -> PolicyCheckResult:
        runway_days = assessment.runway_days_after_action
        if runway_days < float(self.config.min_runway_days):
            return PolicyCheckResult(
                policy_name='runway_protection',
                status='veto',
                reason='runway_veto:min_runway_breached',
                details={
                    'runway_days_after_action': runway_days,
                    'min_runway_days': self.config.min_runway_days,
                    'requested_budget': assessment.requested_budget,
                    'total_encumbrance': assessment.total_encumbrance,
                },
            )
        return PolicyCheckResult(
            policy_name='runway_protection',
            status='allow',
            reason='runway_ok',
            details={
                'runway_days_after_action': runway_days,
                'min_runway_days': self.config.min_runway_days,
                'requested_budget': assessment.requested_budget,
                'total_encumbrance': assessment.total_encumbrance,
            },
        )

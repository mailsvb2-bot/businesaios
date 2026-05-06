from __future__ import annotations

from dataclasses import dataclass, field

from governance.economic.action_economics_model import ActionEconomicsAssessment, ActionEconomicsSnapshot
from governance.economic.economic_policy_contract import EconomicPolicyConfig, PolicyCheckResult

CANON_NON_DECISION_MODULE = True


@dataclass(frozen=True)
class LiquidityPolicy:
    config: EconomicPolicyConfig = field(default_factory=EconomicPolicyConfig)

    def evaluate(self, *, assessment: ActionEconomicsAssessment, snapshot: ActionEconomicsSnapshot) -> PolicyCheckResult:
        explicit_buffer = max(0.0, float(snapshot.required_liquidity_buffer))
        monthly_floor = max(snapshot.protected_cash_reserve, snapshot.monthly_burn * self.config.liquidity_floor_months)
        minimum_liquidity = max(monthly_floor, explicit_buffer)
        if assessment.liquidity_after_action < minimum_liquidity:
            return PolicyCheckResult(
                policy_name='liquidity_policy',
                status='veto',
                reason='liquidity_veto:below_floor',
                details={
                    'liquidity_after_action': assessment.liquidity_after_action,
                    'minimum_liquidity': minimum_liquidity,
                    'monthly_floor': monthly_floor,
                    'explicit_buffer': explicit_buffer,
                    'total_encumbrance': assessment.total_encumbrance,
                },
            )
        return PolicyCheckResult(
            policy_name='liquidity_policy',
            status='allow',
            reason='liquidity_ok',
            details={
                'liquidity_after_action': assessment.liquidity_after_action,
                'minimum_liquidity': minimum_liquidity,
                'monthly_floor': monthly_floor,
                'explicit_buffer': explicit_buffer,
                'total_encumbrance': assessment.total_encumbrance,
            },
        )

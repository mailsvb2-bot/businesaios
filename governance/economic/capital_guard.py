from __future__ import annotations

from dataclasses import dataclass, field

from governance.economic.action_economics_model import ActionEconomicsAssessment, ActionEconomicsSnapshot
from governance.economic.economic_policy_contract import EconomicPolicyConfig, PolicyCheckResult
from governance.economic.liquidity_policy import LiquidityPolicy
from governance.economic.runway_protection import RunwayProtection

CANON_NON_DECISION_MODULE = True


@dataclass(frozen=True)
class CapitalGuard:
    config: EconomicPolicyConfig = field(default_factory=EconomicPolicyConfig)
    runway_protection: RunwayProtection = field(init=False)
    liquidity_policy: LiquidityPolicy = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "runway_protection", RunwayProtection(config=self.config))
        object.__setattr__(self, "liquidity_policy", LiquidityPolicy(config=self.config))

    def evaluate(self, *, assessment: ActionEconomicsAssessment, snapshot: ActionEconomicsSnapshot) -> tuple[PolicyCheckResult, ...]:
        checks: list[PolicyCheckResult] = []
        if assessment.reserve_gap > 0.0:
            checks.append(PolicyCheckResult(
                policy_name="capital_guard",
                status="veto",
                reason="capital_veto:protected_reserve_breached",
                details={
                    "reserve_gap": assessment.reserve_gap,
                    "protected_cash_reserve": snapshot.protected_cash_reserve,
                    "cash_after_action": assessment.cash_after_action,
                },
            ))
        else:
            checks.append(PolicyCheckResult(policy_name="capital_guard", status="allow", reason="capital_reserve_ok", details={"reserve_gap": 0.0}))
        checks.append(self.runway_protection.evaluate(assessment))
        checks.append(self.liquidity_policy.evaluate(assessment=assessment, snapshot=snapshot))
        return tuple(checks)

from __future__ import annotations

from dataclasses import dataclass, field

from governance.economic.action_economics_model import ActionEconomicsAssessment, ActionEconomicsSnapshot
from governance.economic.economic_policy_contract import EconomicPolicyConfig

CANON_NON_DECISION_MODULE = True


@dataclass(frozen=True)
class SurvivalModeDecision:
    mode: str
    reason: str


@dataclass(frozen=True)
class SurvivalModeSwitch:
    config: EconomicPolicyConfig = field(default_factory=EconomicPolicyConfig)

    def evaluate(self, *, assessment: ActionEconomicsAssessment, snapshot: ActionEconomicsSnapshot) -> SurvivalModeDecision:
        if (
            assessment.reserve_gap > 0.0
            or assessment.runway_days_after_action < float(self.config.survival_runway_days)
            or float(snapshot.drawdown_ratio) >= float(self.config.max_drawdown_ratio)
        ):
            return SurvivalModeDecision(mode='survival', reason='survival_mode:cash_preservation')
        if (
            assessment.runway_days_after_action < float(self.config.defensive_runway_days)
            or snapshot.gross_margin < snapshot.target_margin
        ):
            return SurvivalModeDecision(mode='defensive', reason='survival_mode:defensive')
        return SurvivalModeDecision(mode='normal', reason='survival_mode:normal')

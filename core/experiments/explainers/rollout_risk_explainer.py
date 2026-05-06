from __future__ import annotations

from core.experiments.enums import RiskLevel, RolloutDecision


class RolloutRiskExplainer:
    def explain(self, *, risk_level: RiskLevel, decision: RolloutDecision) -> str:
        return f"risk={risk_level.value}; recommended rollout decision={decision.value}"

from __future__ import annotations

from dataclasses import dataclass, field

from ..explainers.budget_decision_explainer import BudgetDecisionExplainer
from ..explainers.margin_risk_explainer import MarginRiskExplainer
from ..explainers.unit_economics_explainer import UnitEconomicsExplainer
from ..types import EconomicsSnapshot


@dataclass
class EconomicsExplanationBuilder:
    unit_economics_explainer: UnitEconomicsExplainer = field(default_factory=UnitEconomicsExplainer)
    budget_decision_explainer: BudgetDecisionExplainer = field(default_factory=BudgetDecisionExplainer)
    margin_risk_explainer: MarginRiskExplainer = field(default_factory=MarginRiskExplainer)

    def build(self, snapshot: EconomicsSnapshot) -> dict[str, str]:
        return {
            "unit_economics": self.unit_economics_explainer.explain(snapshot),
            "budget_decision": self.budget_decision_explainer.explain(snapshot),
            "margin_risk": self.margin_risk_explainer.explain(snapshot),
        }

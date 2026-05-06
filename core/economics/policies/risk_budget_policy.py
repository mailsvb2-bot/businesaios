from __future__ import annotations

from dataclasses import dataclass

from ..enums import BudgetPressureLevel
from ..types import BudgetEnvelope, RiskBudgetAdvice


@dataclass
class RiskBudgetPolicy:
    def advise(self, budget: BudgetEnvelope) -> RiskBudgetAdvice:
        total = max(budget.recommended_spend_cap, 0.0)
        if budget.pressure_level == BudgetPressureLevel.LOW:
            experiment_ratio, reserve_ratio = 0.20, 0.20
        elif budget.pressure_level == BudgetPressureLevel.MEDIUM:
            experiment_ratio, reserve_ratio = 0.12, 0.28
        else:
            experiment_ratio, reserve_ratio = 0.05, 0.40
        experiment_budget = total * experiment_ratio
        reserve_budget = total * reserve_ratio
        core_budget = max(total - experiment_budget - reserve_budget, 0.0)
        return RiskBudgetAdvice(
            experiment_budget=experiment_budget,
            core_budget=core_budget,
            reserve_budget=reserve_budget,
            rationale="Risk budget advice preserves reserve capacity under economics pressure.",
        )

from __future__ import annotations

from dataclasses import dataclass

from ..enums import BudgetPolicyMode, BudgetPressureLevel
from ..types import BudgetAllocationAdvice, BudgetEnvelope


@dataclass
class BudgetAllocationPolicy:
    mode: BudgetPolicyMode = BudgetPolicyMode.BALANCED

    def advise(self, budget: BudgetEnvelope) -> BudgetAllocationAdvice:
        total = max(budget.recommended_spend_cap, 0.0)
        if budget.pressure_level in {BudgetPressureLevel.HIGH, BudgetPressureLevel.EXTREME}:
            allocations = {"core_acquisition": total * 0.45, "retention": total * 0.35, "experiments": total * 0.05, "brand": total * 0.15}
        elif self.mode == BudgetPolicyMode.CONSERVATIVE:
            allocations = {"core_acquisition": total * 0.40, "retention": total * 0.35, "experiments": total * 0.10, "brand": total * 0.15}
        elif self.mode == BudgetPolicyMode.AGGRESSIVE:
            allocations = {"core_acquisition": total * 0.50, "retention": total * 0.20, "experiments": total * 0.20, "brand": total * 0.10}
        else:
            allocations = {"core_acquisition": total * 0.45, "retention": total * 0.25, "experiments": total * 0.15, "brand": total * 0.15}
        return BudgetAllocationAdvice(
            total_recommended_budget=total,
            channel_allocations=allocations,
            rationale="Economics policy is advisory only and must never issue execution decisions.",
        )

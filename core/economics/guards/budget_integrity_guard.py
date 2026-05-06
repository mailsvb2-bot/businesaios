from __future__ import annotations

from dataclasses import dataclass

from ..enums import GuardSeverity
from ..guard import GuardTrigger
from ..types import BudgetEnvelope


@dataclass
class BudgetIntegrityGuard:
    def check(self, budget: BudgetEnvelope) -> GuardTrigger | None:
        if budget.available_growth_budget < 0 or budget.recommended_spend_cap < 0:
            return GuardTrigger(
                code="budget_integrity",
                severity=GuardSeverity.BLOCK,
                message="Budget envelope contains invalid negative values.",
                details={
                    "available_growth_budget": budget.available_growth_budget,
                    "recommended_spend_cap": budget.recommended_spend_cap,
                },
            )
        return None

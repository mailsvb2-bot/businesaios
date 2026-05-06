from __future__ import annotations

from dataclasses import dataclass

from ..enums import GuardSeverity
from ..guard import GuardTrigger
from ..types import BudgetEnvelope, SpendSignal


@dataclass
class OverspendGuard:
    overspend_factor: float = 1.05

    def check(self, spend: SpendSignal, budget: BudgetEnvelope) -> GuardTrigger | None:
        actual_total = spend.marketing_spend + spend.sales_spend + spend.operations_spend
        if actual_total > budget.recommended_spend_cap * self.overspend_factor:
            return GuardTrigger(
                code="overspend",
                severity=GuardSeverity.BLOCK,
                message="Observed spend exceeds recommended cap.",
                details={"actual_total": actual_total, "recommended_cap": budget.recommended_spend_cap},
            )
        return None

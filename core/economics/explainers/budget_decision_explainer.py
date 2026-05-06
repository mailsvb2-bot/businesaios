from __future__ import annotations

from dataclasses import dataclass

from ..types import EconomicsSnapshot


@dataclass
class BudgetDecisionExplainer:
    def explain(self, snapshot: EconomicsSnapshot) -> str:
        budget = snapshot.budget_envelope
        return (
            f"Available growth budget={budget.available_growth_budget:.2f}, "
            f"protected reserve={budget.protected_cash_reserve:.2f}, "
            f"recommended cap={budget.recommended_spend_cap:.2f}, "
            f"pressure={budget.pressure_level.value}."
        )

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..types import BudgetEnvelope, BudgetAllocationAdvice, EconomicAction, EconomicState, RiskBudgetAdvice, SpendCapAdvice
from .budget_allocation_policy import BudgetAllocationPolicy
from .risk_budget_policy import RiskBudgetPolicy
from .spend_cap_policy import SpendCapPolicy


class EconomicPolicy(Protocol):
    policy_id: str

    def propose(self, state: EconomicState) -> EconomicAction:
        ...


@dataclass
class EconomicsPolicySuite:
    budget_allocation_policy: BudgetAllocationPolicy
    spend_cap_policy: SpendCapPolicy
    risk_budget_policy: RiskBudgetPolicy

    def advise(self, budget: BudgetEnvelope) -> dict[str, BudgetAllocationAdvice | SpendCapAdvice | RiskBudgetAdvice]:
        return {
            "budget_allocation": self.budget_allocation_policy.advise(budget),
            "spend_cap": self.spend_cap_policy.advise(budget),
            "risk_budget": self.risk_budget_policy.advise(budget),
        }


__all__ = [
    "EconomicPolicy",
    "EconomicsPolicySuite",
    "BudgetAllocationPolicy",
    "SpendCapPolicy",
    "RiskBudgetPolicy",
]

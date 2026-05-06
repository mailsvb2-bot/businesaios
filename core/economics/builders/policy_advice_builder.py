from __future__ import annotations

from dataclasses import dataclass, field

from ..policies import BudgetAllocationPolicy, EconomicsPolicySuite, RiskBudgetPolicy, SpendCapPolicy
from ..types import BudgetEnvelope


@dataclass
class EconomicsPolicyAdviceBuilder:
    policy_suite: EconomicsPolicySuite = field(default_factory=lambda: EconomicsPolicySuite(
        budget_allocation_policy=BudgetAllocationPolicy(),
        spend_cap_policy=SpendCapPolicy(),
        risk_budget_policy=RiskBudgetPolicy(),
    ))

    def build(self, budget: BudgetEnvelope) -> dict:
        return self.policy_suite.advise(budget)

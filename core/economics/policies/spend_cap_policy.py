from __future__ import annotations

from dataclasses import dataclass, field

from config.economics_spend_cap_policy import (
    DEFAULT_ECONOMICS_SPEND_CAP_POLICY_DEFAULTS,
    EconomicsSpendCapPolicyDefaults,
)
from ..types import BudgetEnvelope, SpendCapAdvice


@dataclass
class SpendCapPolicy:
    soft_cap_ratio: float | None = None
    policy_defaults: EconomicsSpendCapPolicyDefaults = field(default_factory=lambda: DEFAULT_ECONOMICS_SPEND_CAP_POLICY_DEFAULTS)

    def __post_init__(self) -> None:
        if self.soft_cap_ratio is None:
            self.soft_cap_ratio = self.policy_defaults.soft_cap_ratio

    def advise(self, budget: BudgetEnvelope) -> SpendCapAdvice:
        hard_cap = max(budget.recommended_spend_cap, self.policy_defaults.zero_amount)
        return SpendCapAdvice(
            hard_cap=hard_cap,
            soft_cap=hard_cap * self.soft_cap_ratio,
            rationale='Soft cap is an advisory pre-limit; hard cap is the maximum recommended spend.',
        )

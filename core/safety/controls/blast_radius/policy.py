from __future__ import annotations

from dataclasses import dataclass, field

from .models import BlastRadiusBudget


@dataclass(frozen=True)
class BlastRadiusPolicy:
    default_budget: BlastRadiusBudget
    per_prefix_budget: dict[str, BlastRadiusBudget] = field(default_factory=dict)

    def budget_for(self, action: str) -> BlastRadiusBudget:
        name = str(action or "")
        for prefix, budget in self.per_prefix_budget.items():
            if name.startswith(prefix):
                return budget
        return self.default_budget

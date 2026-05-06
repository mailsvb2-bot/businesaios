from __future__ import annotations

from dataclasses import dataclass

from contracts.autopilot_contract import AutopilotConstraints


@dataclass(frozen=True)
class ConstraintsBudget:
    daily_budget_minor: int
    currency: str


@dataclass(frozen=True)
class CampaignBudgetPolicy:
    """Resolve 7-day and daily budgets from autopilot constraints + request.

    NOTE: core.growth.budget_guardrails.DailyLimits is about spend-safety and
    is not a per-tenant budgeting contract. Here we only need a deterministic
    clamp based on AutopilotConstraints.daily_budget_minor.
    """

    def budget_from_constraints(self, c: AutopilotConstraints) -> ConstraintsBudget:
        return ConstraintsBudget(daily_budget_minor=int(c.daily_budget_minor or 0), currency=str(c.currency or "RUB"))

    def clamp_total_budget_minor_7d(self, *, total_budget_minor_7d: int, constraints: ConstraintsBudget) -> int:
        daily = int(constraints.daily_budget_minor or 0)
        if daily <= 0:
            return int(total_budget_minor_7d)
        max_total = int(daily) * 7
        return min(int(total_budget_minor_7d), int(max_total))

    def daily_budget_minor_from_total_7d(self, *, total_budget_minor_7d: int) -> int:
        # Keep 7d -> daily rounding consistent with TrafficStrategyService allocator.
        return int(total_budget_minor_7d) // 7

from __future__ import annotations

from dataclasses import dataclass

from acquisition.funnel_model import FunnelSnapshot
from shared.numbers import coerce_float, coerce_int

CANON_ACQUISITION_BUDGET_OPTIMIZER = True


@dataclass(frozen=True, slots=True)
class BudgetOptimizerInputs:
    target_customers: int
    cost_per_entry: float
    funnel: FunnelSnapshot
    setup_cost: float = 0.0
    target_days: float = 0.0
    available_budget: float = 0.0


@dataclass(frozen=True, slots=True)
class BudgetRecommendation:
    required_entries: int
    required_budget: float
    recommended_daily_budget: float
    budget_gap: float
    is_budget_sufficient: bool
    reasons: tuple[str, ...]


class BudgetOptimizer:
    def recommend(self, inputs: BudgetOptimizerInputs) -> BudgetRecommendation:
        target_customers = coerce_int(inputs.target_customers, 0, minimum=0)
        cost_per_entry = coerce_float(inputs.cost_per_entry, 0.0, minimum=0.0)
        setup_cost = coerce_float(inputs.setup_cost, 0.0, minimum=0.0)
        target_days = coerce_float(inputs.target_days, 0.0, minimum=0.0)
        available_budget = coerce_float(inputs.available_budget, 0.0, minimum=0.0)

        required_entries = inputs.funnel.required_entries_for_customers(target_customers)
        required_budget = 0.0 if required_entries <= 0 or cost_per_entry <= 0.0 else required_entries * cost_per_entry + setup_cost
        pacing_days = target_days if target_days > 0.0 else max(inputs.funnel.avg_cycle_days, 1.0)
        recommended_daily_budget = required_budget / pacing_days if pacing_days > 0.0 else required_budget
        budget_gap = max(0.0, required_budget - available_budget)

        reasons: list[str] = []
        if inputs.funnel.overall_conversion_rate <= 0.0 and target_customers > 0:
            reasons.append("zero_funnel_conversion")
        if cost_per_entry <= 0.0 and required_entries > 0:
            reasons.append("zero_cost_per_entry_assumption")
        if budget_gap > 0.0:
            reasons.append("budget_below_required")

        return BudgetRecommendation(
            required_entries=required_entries,
            required_budget=round(required_budget, 4),
            recommended_daily_budget=round(recommended_daily_budget, 4),
            budget_gap=round(budget_gap, 4),
            is_budget_sufficient=budget_gap <= 0.0,
            reasons=tuple(reasons),
        )

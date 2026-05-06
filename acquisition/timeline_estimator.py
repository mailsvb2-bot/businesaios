from __future__ import annotations

import math
from dataclasses import dataclass

from acquisition.funnel_model import FunnelSnapshot
from shared.numbers import coerce_float, coerce_int

CANON_ACQUISITION_TIMELINE_ESTIMATOR = True


@dataclass(frozen=True, slots=True)
class TimelineEstimatorInputs:
    target_customers: int
    total_budget: float
    daily_budget: float
    cost_per_entry: float
    funnel: FunnelSnapshot
    target_days: float = 0.0
    setup_cost: float = 0.0


@dataclass(frozen=True, slots=True)
class TimelineEstimate:
    required_entries: int
    affordable_entries: int
    affordable_customers: int
    days_to_fill_top_of_funnel: float
    estimated_days: float
    feasible_in_target_window: bool
    constrained_by: str
    reasons: tuple[str, ...]


class TimelineEstimator:
    def estimate(self, inputs: TimelineEstimatorInputs) -> TimelineEstimate:
        target_customers = coerce_int(inputs.target_customers, 0, minimum=0)
        total_budget = coerce_float(inputs.total_budget, 0.0, minimum=0.0)
        daily_budget = coerce_float(inputs.daily_budget, 0.0, minimum=0.0)
        cost_per_entry = coerce_float(inputs.cost_per_entry, 0.0, minimum=0.0)
        target_days = coerce_float(inputs.target_days, 0.0, minimum=0.0)
        setup_cost = coerce_float(inputs.setup_cost, 0.0, minimum=0.0)

        required_entries = inputs.funnel.required_entries_for_customers(target_customers)
        spendable_budget = max(0.0, total_budget - setup_cost)

        if cost_per_entry <= 0.0:
            affordable_entries = 0 if required_entries > 0 else 0
            entries_per_day = 0.0
        else:
            affordable_entries = int(spendable_budget / cost_per_entry)
            entries_per_day = daily_budget / cost_per_entry if daily_budget > 0.0 else 0.0

        affordable_customers = inputs.funnel.expected_customers_from_entries(affordable_entries)

        if required_entries <= 0:
            days_to_fill = 0.0
        elif entries_per_day <= 0.0:
            days_to_fill = math.inf
        else:
            days_to_fill = required_entries / entries_per_day

        estimated_days = max(days_to_fill, inputs.funnel.avg_cycle_days) if required_entries > 0 else inputs.funnel.avg_cycle_days

        reasons: list[str] = []
        constrained_by = "balanced"
        if inputs.funnel.overall_conversion_rate <= 0.0 and target_customers > 0:
            constrained_by = "funnel_conversion"
            reasons.append("zero_funnel_conversion")
        elif affordable_customers < target_customers:
            constrained_by = "total_budget"
            reasons.append("budget_cannot_buy_enough_entries")
        if cost_per_entry <= 0.0 and required_entries > 0:
            reasons.append("zero_cost_per_entry_assumption")
        if constrained_by not in {"funnel_conversion", "total_budget"} and not math.isfinite(days_to_fill):
            constrained_by = "daily_budget"
            reasons.append("no_daily_budget_pacing")
        elif constrained_by not in {"funnel_conversion", "total_budget"} and days_to_fill > inputs.funnel.avg_cycle_days:
            constrained_by = "daily_budget"
        elif constrained_by == "balanced" and inputs.funnel.avg_cycle_days > 0.0:
            constrained_by = "funnel_cycle"

        feasible_in_target_window = True
        if target_days > 0.0 and (not math.isfinite(estimated_days) or estimated_days > target_days):
            feasible_in_target_window = False
            reasons.append("timeline_exceeds_target_window")

        return TimelineEstimate(
            required_entries=required_entries,
            affordable_entries=affordable_entries,
            affordable_customers=affordable_customers,
            days_to_fill_top_of_funnel=round(days_to_fill, 4) if math.isfinite(days_to_fill) else math.inf,
            estimated_days=round(estimated_days, 4) if math.isfinite(estimated_days) else math.inf,
            feasible_in_target_window=feasible_in_target_window,
            constrained_by=constrained_by,
            reasons=tuple(reasons),
        )

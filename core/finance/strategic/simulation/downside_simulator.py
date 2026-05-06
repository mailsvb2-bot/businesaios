from __future__ import annotations

from decimal import Decimal

from config.strategic_finance_simulation_policy import (
    DEFAULT_DOWNSIDE_SIMULATOR_POLICY,
    DownsideSimulatorPolicy,
)
from core.finance.strategic.decimal_utils import q2


class DownsideSimulator:
    def __init__(self, policy: DownsideSimulatorPolicy = DEFAULT_DOWNSIDE_SIMULATOR_POLICY) -> None:
        self._policy = policy

    def run(
        self,
        revenue: Decimal,
        costs: Decimal,
        downside_revenue: Decimal | None = None,
        downside_cost: Decimal | None = None,
    ) -> dict[str, Decimal]:
        revenue_drop = self._policy.default_downside_revenue if downside_revenue is None else downside_revenue
        cost_increase = self._policy.default_downside_cost if downside_cost is None else downside_cost
        stressed_revenue = q2(revenue * (self._policy.baseline_multiplier - revenue_drop))
        stressed_costs = q2(costs * (self._policy.baseline_multiplier + cost_increase))
        return {
            'revenue': stressed_revenue,
            'costs': stressed_costs,
            'margin': q2(stressed_revenue - stressed_costs),
        }

from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2
from core.finance.strategic.types import Scenario


class DeterministicSimulator:
    def run(self, base_revenue: Decimal, base_costs: Decimal, scenario: Scenario) -> dict[str, Decimal]:
        revenue = q2(base_revenue * scenario.revenue_multiplier)
        costs = q2(base_costs * scenario.cost_multiplier)
        return {'revenue': revenue, 'costs': costs, 'margin': q2(revenue - costs)}

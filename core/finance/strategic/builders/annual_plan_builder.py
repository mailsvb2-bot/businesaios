from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class AnnualPlanBuilder:
    def build(self, revenue: list[Decimal], costs: list[Decimal]) -> dict[str, Decimal]:
        total_revenue = q2(sum(revenue, start=Decimal('0')))
        total_costs = q2(sum(costs, start=Decimal('0')))
        return {
            'revenue': total_revenue,
            'costs': total_costs,
            'margin': q2(total_revenue - total_costs),
        }

from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class QuarterlyPlanBuilder:
    def build(self, revenue: list[Decimal], costs: list[Decimal]) -> list[dict[str, Decimal | int]]:
        result: list[dict[str, Decimal | int]] = []
        for index in range(0, min(len(revenue), len(costs)), 3):
            quarter_revenue = q2(sum(revenue[index:index + 3], start=Decimal('0')))
            quarter_costs = q2(sum(costs[index:index + 3], start=Decimal('0')))
            result.append({
                'quarter': (index // 3) + 1,
                'revenue': quarter_revenue,
                'costs': quarter_costs,
                'margin': q2(quarter_revenue - quarter_costs),
            })
        return result

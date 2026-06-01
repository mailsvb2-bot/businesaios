from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class MarginForecastBuilder:
    def build(self, revenue: list[Decimal], costs: list[Decimal]) -> list[Decimal]:
        if len(revenue) != len(costs):
            raise ValueError("revenue and costs must have equal length")
        return [q2(rev - cost) for rev, cost in zip(revenue, costs, strict=False)]

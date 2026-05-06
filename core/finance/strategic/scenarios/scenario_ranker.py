from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import Scenario


class ScenarioRanker:
    def rank(self, scenarios: tuple[Scenario, ...]) -> tuple[Scenario, ...]:
        return tuple(sorted(scenarios, key=self._rank_key, reverse=True))

    def _rank_key(self, item: Scenario) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        growth_efficiency = (item.revenue_multiplier - item.cost_multiplier) * item.probability
        resilience = item.capital_efficiency_bias - item.downside_risk
        pressure_penalty = item.cash_pressure + item.working_capital_pressure + item.margin_deterioration + item.channel_decay
        downside_depth = sum(item.downside_tree_weights.values(), start=Decimal('0'))
        return (growth_efficiency, resilience, -pressure_penalty, -downside_depth)

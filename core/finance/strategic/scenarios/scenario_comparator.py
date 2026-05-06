from __future__ import annotations

from core.finance.strategic.types import Scenario


class ScenarioComparator:
    def compare(self, left: Scenario, right: Scenario) -> dict:
        return {
            'revenue_delta': round(left.revenue_multiplier - right.revenue_multiplier, 4),
            'cost_delta': round(left.cost_multiplier - right.cost_multiplier, 4),
            'probability_delta': round(left.probability - right.probability, 4),
            'runway_quality_delta': round(left.capital_efficiency_bias - right.capital_efficiency_bias, 4),
            'risk_delta': round(right.downside_risk - left.downside_risk, 4),
            'working_capital_delta': round(right.working_capital_pressure - left.working_capital_pressure, 4),
            'downside_depth_delta': round(sum(right.downside_tree_weights.values()) - sum(left.downside_tree_weights.values()), 4),
            'product_scope_delta': len(left.product_bias) - len(right.product_bias),
            'entity_scope_delta': len(left.entity_bias) - len(right.entity_bias),
        }

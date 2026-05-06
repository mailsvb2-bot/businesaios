from __future__ import annotations

from dataclasses import dataclass, field

from config.economics_evaluation_policy import (
    DEFAULT_UNIT_ECONOMICS_BUILDER_POLICY,
    UnitEconomicsBuilderPolicy,
)

from ..types import CostSignal, CustomerValueSignal, RevenueSignal, UnitEconomics


@dataclass
class UnitEconomicsBuilder:
    policy: UnitEconomicsBuilderPolicy = field(default_factory=lambda: DEFAULT_UNIT_ECONOMICS_BUILDER_POLICY)

    def build(
        self,
        *,
        revenue: RevenueSignal,
        cost: CostSignal,
        customer_value: CustomerValueSignal,
    ) -> UnitEconomics:
        zero_ratio = self.policy.zero_ratio
        period_days = max(revenue.period_days, self.policy.minimum_period_days)
        active_customers = max(customer_value.active_customers, self.policy.minimum_active_customers)
        gross_profit = revenue.net_revenue - cost.cogs
        contribution_profit = revenue.net_revenue - cost.cogs - cost.variable_costs
        contribution_margin_ratio = contribution_profit / revenue.net_revenue if revenue.net_revenue > zero_ratio else zero_ratio
        revenue_per_customer = revenue.net_revenue / active_customers if active_customers > self.policy.minimum_active_customers else zero_ratio
        contribution_per_customer_period = revenue_per_customer * contribution_margin_ratio
        contribution_per_customer_day = contribution_per_customer_period / period_days
        variable_cost_ratio = cost.variable_costs / revenue.net_revenue if revenue.net_revenue > zero_ratio else zero_ratio
        return UnitEconomics(
            gross_profit=gross_profit,
            contribution_profit=contribution_profit,
            contribution_margin_ratio=contribution_margin_ratio,
            revenue_per_customer=revenue_per_customer,
            contribution_per_customer_period=contribution_per_customer_period,
            contribution_per_customer_day=contribution_per_customer_day,
            variable_cost_ratio=variable_cost_ratio,
            period_days=period_days,
        )

from __future__ import annotations

from dataclasses import dataclass, field

from config.economics_evaluation_policy import DEFAULT_MARGIN_BUILDER_POLICY, MarginBuilderPolicy

from ..enums import MarginHealthStatus
from ..types import CostSignal, MarginSnapshot, RevenueSignal, SpendSignal


@dataclass
class MarginBuilder:
    policy: MarginBuilderPolicy = field(default_factory=lambda: DEFAULT_MARGIN_BUILDER_POLICY)

    def build(self, *, revenue: RevenueSignal, cost: CostSignal, spend: SpendSignal) -> MarginSnapshot:
        zero_ratio = self.policy.zero_ratio
        gross_margin_ratio = (revenue.net_revenue - cost.cogs) / revenue.net_revenue if revenue.net_revenue > zero_ratio else zero_ratio
        total_cost = cost.cogs + cost.fixed_costs + cost.variable_costs + spend.marketing_spend + spend.sales_spend + spend.operations_spend
        net_margin_ratio = (revenue.net_revenue - total_cost) / revenue.net_revenue if revenue.net_revenue > zero_ratio else zero_ratio
        if net_margin_ratio < zero_ratio:
            status = MarginHealthStatus.NEGATIVE
        elif net_margin_ratio < self.policy.weak_net_margin_threshold:
            status = MarginHealthStatus.WEAK
        elif net_margin_ratio < self.policy.stable_net_margin_threshold:
            status = MarginHealthStatus.STABLE
        else:
            status = MarginHealthStatus.STRONG
        return MarginSnapshot(gross_margin_ratio=gross_margin_ratio, net_margin_ratio=net_margin_ratio, status=status)

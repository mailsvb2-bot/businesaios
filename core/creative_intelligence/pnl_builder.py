from __future__ import annotations

from config.creative_pnl_policy import DEFAULT_CREATIVE_PNL_POLICY, CreativePnLPolicy
from core.creative_intelligence.attribution_credit import attributed_revenue
from core.creative_intelligence.models import CreativeEconomicsInput, CreativePnLSnapshot


def _clamp_margin_ratio(value: float, *, policy: CreativePnLPolicy) -> float:
    return max(float(policy.min_margin_ratio), min(float(policy.max_margin_ratio), float(value)))


def build_pnl_snapshot(
    item: CreativeEconomicsInput,
    *,
    policy: CreativePnLPolicy | None = None,
) -> CreativePnLSnapshot:
    policy = policy or DEFAULT_CREATIVE_PNL_POLICY
    revenue = attributed_revenue(
        revenue=item.revenue,
        attribution_credit=item.attribution_credit,
    )
    total_cost = max(
        float(policy.min_cost),
        item.spend + item.cogs + item.variable_cost + item.fixed_cost_share,
    )
    contribution_profit = revenue - total_cost
    margin_ratio = (
        float(policy.default_margin_ratio)
        if revenue <= float(policy.min_revenue_for_margin)
        else _clamp_margin_ratio(contribution_profit / revenue, policy=policy)
    )
    roi = (
        float(policy.default_roi)
        if total_cost <= float(policy.min_total_cost_for_roi)
        else contribution_profit / total_cost
    )
    return CreativePnLSnapshot(
        creative_id=item.creative_id,
        attributed_revenue=revenue,
        total_cost=total_cost,
        contribution_profit=contribution_profit,
        contribution_margin_ratio=margin_ratio,
        roi=roi,
    )

from __future__ import annotations

from config.creative_portfolio_policy import (
    DEFAULT_ECONOMICS_STATE_BUILDER_POLICY,
    EconomicsStateBuilderPolicy,
)
from core.creative_intelligence.models import CreativeIntelligenceSnapshot


def build_economics_state(
    snapshots: tuple[CreativeIntelligenceSnapshot, ...],
    policy: EconomicsStateBuilderPolicy = DEFAULT_ECONOMICS_STATE_BUILDER_POLICY,
) -> dict[str, float]:
    if not snapshots:
        return {
            "portfolio_roi_mean": float(policy.zero_value),
            "portfolio_profit_sum": float(policy.zero_value),
            "portfolio_downside_mean": float(policy.zero_value),
        }

    roi_mean = sum(float(item.pnl.roi) for item in snapshots) / float(len(snapshots))
    profit_sum = sum(float(item.pnl.contribution_profit) for item in snapshots)
    downside_mean = sum(float(item.downside_envelope) for item in snapshots) / float(len(snapshots))
    return {
        "portfolio_roi_mean": roi_mean,
        "portfolio_profit_sum": profit_sum,
        "portfolio_downside_mean": downside_mean,
    }

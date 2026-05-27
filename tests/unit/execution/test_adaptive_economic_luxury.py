from execution.capital_rebalancer import CapitalRebalancer
from execution.channel_roi_memory import ChannelROIMemory
from execution.portfolio_allocator import PortfolioAllocator
from execution.pre_action_economic_forecast import PreActionEconomicForecastBuilder


def test_pre_action_forecast_uses_channel_memory() -> None:
    memory = ChannelROIMemory().from_records(
        channel="ads",
        action_type="launch_campaign",
        records=[
            {"kind": "economic_feedback", "channel": "ads", "action_type": "launch_campaign", "expected_roi": 0.4, "realized_revenue": 150.0, "verified": True},
            {"kind": "economic_feedback", "channel": "ads", "action_type": "launch_campaign", "expected_roi": 0.3, "realized_revenue": 100.0, "verified": True},
        ],
    )
    forecast = PreActionEconomicForecastBuilder().build(
        expected_roi=0.5,
        requested_budget=100.0,
        current_survival_mode="normal",
        runway_days_after_action=120.0,
        memory=memory,
    )
    payload = forecast.to_dict()
    assert payload["confidence"]["confidence"] > 0.0
    assert payload["prediction"]["upside_roi"] >= payload["prediction"]["downside_roi"]


def test_portfolio_allocator_and_rebalancer_are_read_only_helpers() -> None:
    allocator = PortfolioAllocator()
    plan = allocator.plan(
        portfolio_signals={
            "alpha": {"adjusted_roi": 0.6, "confidence": 0.9},
            "beta": {"adjusted_roi": 0.2, "confidence": 0.5},
        }
    )
    assert len(plan.allocations) == 2
    rebalance = CapitalRebalancer().build_plan(
        portfolio_signals={
            "alpha": {"adjusted_roi": 0.6, "confidence": 0.9},
            "beta": {"adjusted_roi": 0.2, "confidence": 0.5},
        },
        current_allocations={"alpha": 0.4, "beta": 0.6},
    )
    assert len(rebalance.deltas) == 2

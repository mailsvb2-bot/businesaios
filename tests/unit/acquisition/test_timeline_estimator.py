from __future__ import annotations

import math

from acquisition.funnel_model import FunnelModel, FunnelStage
from acquisition.timeline_estimator import TimelineEstimator, TimelineEstimatorInputs


def _funnel_snapshot():
    return FunnelModel().summarize((FunnelStage(name="visit_to_lead", conversion_rate=0.5, avg_stage_days=3.0), FunnelStage(name="lead_to_sale", conversion_rate=0.2, avg_stage_days=7.0)))


def test_timeline_estimator_calculates_duration_from_budget_pacing() -> None:
    result = TimelineEstimator().estimate(TimelineEstimatorInputs(target_customers=10, total_budget=300.0, daily_budget=20.0, cost_per_entry=2.0, funnel=_funnel_snapshot(), target_days=15.0))
    assert result.required_entries == 100
    assert result.affordable_entries == 150
    assert result.affordable_customers == 15
    assert result.days_to_fill_top_of_funnel == 10.0
    assert result.estimated_days == 10.0
    assert result.constrained_by in {"daily_budget", "funnel_cycle", "balanced"}
    assert result.feasible_in_target_window is True


def test_timeline_estimator_accounts_for_setup_cost_in_affordable_entries() -> None:
    result = TimelineEstimator().estimate(TimelineEstimatorInputs(target_customers=10, total_budget=300.0, daily_budget=20.0, cost_per_entry=2.0, funnel=_funnel_snapshot(), target_days=30.0, setup_cost=100.0))
    assert result.affordable_entries == 100
    assert result.affordable_customers == 10


def test_timeline_estimator_marks_total_budget_constraint() -> None:
    result = TimelineEstimator().estimate(TimelineEstimatorInputs(target_customers=10, total_budget=100.0, daily_budget=50.0, cost_per_entry=2.0, funnel=_funnel_snapshot(), target_days=30.0))
    assert result.constrained_by == "total_budget"
    assert "budget_cannot_buy_enough_entries" in result.reasons


def test_timeline_estimator_marks_no_daily_budget_as_infinite_timeline() -> None:
    result = TimelineEstimator().estimate(TimelineEstimatorInputs(target_customers=10, total_budget=1000.0, daily_budget=0.0, cost_per_entry=2.0, funnel=_funnel_snapshot(), target_days=30.0))
    assert result.constrained_by == "daily_budget"
    assert math.isinf(result.days_to_fill_top_of_funnel)
    assert math.isinf(result.estimated_days)
    assert result.feasible_in_target_window is False
    assert "no_daily_budget_pacing" in result.reasons
    assert "timeline_exceeds_target_window" in result.reasons


def test_timeline_estimator_handles_zero_cost_per_entry_conservatively() -> None:
    result = TimelineEstimator().estimate(TimelineEstimatorInputs(target_customers=10, total_budget=100.0, daily_budget=10.0, cost_per_entry=0.0, funnel=_funnel_snapshot()))
    assert result.required_entries == 100
    assert result.affordable_entries == 0
    assert result.affordable_customers == 0
    assert result.constrained_by == "total_budget"
    assert math.isinf(result.days_to_fill_top_of_funnel)
    assert math.isinf(result.estimated_days)
    assert "zero_cost_per_entry_assumption" in result.reasons
    assert "budget_cannot_buy_enough_entries" in result.reasons


def test_timeline_estimator_preserves_funnel_conversion_as_primary_constraint() -> None:
    funnel = FunnelModel().summarize((FunnelStage(name="dead", conversion_rate=0.0, avg_stage_days=3.0),))
    result = TimelineEstimator().estimate(TimelineEstimatorInputs(target_customers=10, total_budget=1000.0, daily_budget=100.0, cost_per_entry=2.0, funnel=funnel, target_days=30.0))
    assert result.required_entries == 0
    assert result.affordable_entries == 500
    assert result.affordable_customers == 0
    assert result.constrained_by == "funnel_conversion"
    assert "zero_funnel_conversion" in result.reasons

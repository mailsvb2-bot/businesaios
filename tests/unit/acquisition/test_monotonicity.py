from __future__ import annotations

from acquisition.budget_optimizer import BudgetOptimizer, BudgetOptimizerInputs
from acquisition.cac_model import CacInputs, CustomerAcquisitionCostModel
from acquisition.feasibility_solver import AcquisitionFeasibilityRequest, FeasibilitySolver
from acquisition.funnel_model import FunnelModel, FunnelSnapshot, FunnelStage
from acquisition.timeline_estimator import TimelineEstimator, TimelineEstimatorInputs


def _funnel_snapshot(
    conversion_rate_1: float = 0.2,
    conversion_rate_2: float = 0.5,
    conversion_rate_3: float = 0.5,
) -> FunnelSnapshot:
    return FunnelModel().summarize(
        (
            FunnelStage(name="traffic_to_lead", conversion_rate=conversion_rate_1, avg_stage_days=3.0, touchpoints=1),
            FunnelStage(name="lead_to_meeting", conversion_rate=conversion_rate_2, avg_stage_days=4.0, touchpoints=2),
            FunnelStage(name="meeting_to_sale", conversion_rate=conversion_rate_3, avg_stage_days=7.0, touchpoints=3),
        )
    )


def _request(
    *,
    target_customers: int = 10,
    total_budget: float = 2200.0,
    daily_budget: float = 200.0,
    cost_per_entry: float = 10.0,
    gross_margin_ltv: float = 1000.0,
    target_days: float = 20.0,
    setup_cost: float = 100.0,
    expected_monthly_margin_per_customer: float = 100.0,
    stages: tuple[FunnelStage, ...] | None = None,
) -> AcquisitionFeasibilityRequest:
    return AcquisitionFeasibilityRequest(
        target_customers=target_customers,
        total_budget=total_budget,
        daily_budget=daily_budget,
        cost_per_entry=cost_per_entry,
        gross_margin_ltv=gross_margin_ltv,
        stages=stages
        or (
            FunnelStage(name="traffic_to_lead", conversion_rate=0.2, avg_stage_days=3.0, touchpoints=1),
            FunnelStage(name="lead_to_meeting", conversion_rate=0.5, avg_stage_days=4.0, touchpoints=2),
            FunnelStage(name="meeting_to_sale", conversion_rate=0.5, avg_stage_days=7.0, touchpoints=3),
        ),
        target_days=target_days,
        setup_cost=setup_cost,
        expected_monthly_margin_per_customer=expected_monthly_margin_per_customer,
    )


def test_budget_optimizer_required_budget_is_monotonic_with_cost_per_entry() -> None:
    optimizer = BudgetOptimizer()
    funnel = _funnel_snapshot()

    low_cpe = optimizer.recommend(
        BudgetOptimizerInputs(
            target_customers=10,
            cost_per_entry=5.0,
            funnel=funnel,
            setup_cost=100.0,
            target_days=20.0,
            available_budget=0.0,
        )
    )
    high_cpe = optimizer.recommend(
        BudgetOptimizerInputs(
            target_customers=10,
            cost_per_entry=10.0,
            funnel=funnel,
            setup_cost=100.0,
            target_days=20.0,
            available_budget=0.0,
        )
    )

    assert high_cpe.required_entries == low_cpe.required_entries
    assert high_cpe.required_budget >= low_cpe.required_budget


def test_budget_optimizer_required_entries_are_monotonic_with_worse_conversion() -> None:
    optimizer = BudgetOptimizer()
    better_funnel = _funnel_snapshot(0.4, 0.5, 0.5)
    worse_funnel = _funnel_snapshot(0.2, 0.5, 0.5)

    better = optimizer.recommend(
        BudgetOptimizerInputs(
            target_customers=10,
            cost_per_entry=10.0,
            funnel=better_funnel,
            setup_cost=0.0,
            target_days=20.0,
            available_budget=0.0,
        )
    )
    worse = optimizer.recommend(
        BudgetOptimizerInputs(
            target_customers=10,
            cost_per_entry=10.0,
            funnel=worse_funnel,
            setup_cost=0.0,
            target_days=20.0,
            available_budget=0.0,
        )
    )

    assert worse.required_entries >= better.required_entries
    assert worse.required_budget >= better.required_budget


def test_timeline_affordable_entries_are_monotonic_with_total_budget() -> None:
    estimator = TimelineEstimator()
    funnel = _funnel_snapshot()

    lower_budget = estimator.estimate(
        TimelineEstimatorInputs(
            target_customers=10,
            total_budget=1100.0,
            daily_budget=100.0,
            cost_per_entry=10.0,
            funnel=funnel,
            target_days=30.0,
            setup_cost=100.0,
        )
    )
    higher_budget = estimator.estimate(
        TimelineEstimatorInputs(
            target_customers=10,
            total_budget=2100.0,
            daily_budget=100.0,
            cost_per_entry=10.0,
            funnel=funnel,
            target_days=30.0,
            setup_cost=100.0,
        )
    )

    assert higher_budget.affordable_entries >= lower_budget.affordable_entries
    assert higher_budget.affordable_customers >= lower_budget.affordable_customers


def test_timeline_affordable_entries_are_antitonic_with_setup_cost() -> None:
    estimator = TimelineEstimator()
    funnel = _funnel_snapshot()

    lower_setup = estimator.estimate(
        TimelineEstimatorInputs(
            target_customers=10,
            total_budget=2200.0,
            daily_budget=200.0,
            cost_per_entry=10.0,
            funnel=funnel,
            target_days=30.0,
            setup_cost=100.0,
        )
    )
    higher_setup = estimator.estimate(
        TimelineEstimatorInputs(
            target_customers=10,
            total_budget=2200.0,
            daily_budget=200.0,
            cost_per_entry=10.0,
            funnel=funnel,
            target_days=30.0,
            setup_cost=500.0,
        )
    )

    assert higher_setup.affordable_entries <= lower_setup.affordable_entries
    assert higher_setup.affordable_customers <= lower_setup.affordable_customers


def test_cac_is_antitonic_to_acquired_customers_at_fixed_budget() -> None:
    model = CustomerAcquisitionCostModel()

    lower = model.evaluate(
        CacInputs(
            total_budget=1000.0,
            acquired_customers=10,
            gross_margin_ltv=1000.0,
            expected_monthly_margin_per_customer=100.0,
            setup_cost=100.0,
        )
    )
    higher = model.evaluate(
        CacInputs(
            total_budget=1000.0,
            acquired_customers=20,
            gross_margin_ltv=1000.0,
            expected_monthly_margin_per_customer=100.0,
            setup_cost=100.0,
        )
    )

    assert higher.blended_cac <= lower.blended_cac
    assert higher.variable_cac <= lower.variable_cac


def test_solver_feasibility_is_monotonic_with_more_budget_in_baseline_case() -> None:
    low = FeasibilitySolver().solve(_request(total_budget=1200.0))
    high = FeasibilitySolver().solve(_request(total_budget=2200.0))

    assert high.timeline.affordable_customers >= low.timeline.affordable_customers
    assert high.required_budget == low.required_budget
    assert high.feasibility_score >= low.feasibility_score

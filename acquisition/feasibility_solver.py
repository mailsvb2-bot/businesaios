from __future__ import annotations

from dataclasses import dataclass, field

from config.scoring_behavior_policy import AcquisitionFeasibilityPolicy, DEFAULT_ACQUISITION_FEASIBILITY_POLICY
from acquisition.budget_optimizer import BudgetOptimizer, BudgetOptimizerInputs, BudgetRecommendation
from acquisition.cac_model import CacInputs, CacSnapshot, CustomerAcquisitionCostModel
from acquisition.funnel_model import FunnelModel, FunnelSnapshot, FunnelStage
from acquisition.timeline_estimator import TimelineEstimate, TimelineEstimator, TimelineEstimatorInputs
from shared.numbers import coerce_float, coerce_int

CANON_ACQUISITION_FEASIBILITY_SOLVER = True


@dataclass(frozen=True, slots=True)
class AcquisitionFeasibilityRequest:
    target_customers: int
    total_budget: float
    daily_budget: float
    cost_per_entry: float
    gross_margin_ltv: float
    stages: tuple[FunnelStage, ...]
    target_days: float = 0.0
    setup_cost: float = 0.0
    max_cac_to_ltv_ratio: float = 0.33
    payback_horizon_months: float = 12.0
    expected_monthly_margin_per_customer: float = 0.0


@dataclass(frozen=True, slots=True)
class AcquisitionFeasibilityResult:
    feasible: bool
    summary: str
    reasons: tuple[str, ...]
    feasibility_score: float
    customer_gap: int
    budget_gap: float
    required_budget: float
    recommended_daily_budget: float
    estimated_days: float
    funnel: FunnelSnapshot
    budget: BudgetRecommendation
    timeline: TimelineEstimate
    cac: CacSnapshot


class FeasibilitySolver:
    def __init__(self, *, policy: AcquisitionFeasibilityPolicy = DEFAULT_ACQUISITION_FEASIBILITY_POLICY) -> None:
        self._policy = policy
        self._funnel_model = FunnelModel()
        self._budget_optimizer = BudgetOptimizer()
        self._timeline_estimator = TimelineEstimator()
        self._cac_model = CustomerAcquisitionCostModel()

    def solve(self, request: AcquisitionFeasibilityRequest) -> AcquisitionFeasibilityResult:
        target_customers = coerce_int(request.target_customers, 0, minimum=0)
        total_budget = coerce_float(request.total_budget, 0.0, minimum=0.0)
        daily_budget = coerce_float(request.daily_budget, 0.0, minimum=0.0)
        cost_per_entry = coerce_float(request.cost_per_entry, 0.0, minimum=0.0)
        gross_margin_ltv = coerce_float(request.gross_margin_ltv, 0.0, minimum=0.0)
        target_days = coerce_float(request.target_days, 0.0, minimum=0.0)
        setup_cost = coerce_float(request.setup_cost, 0.0, minimum=0.0)
        max_cac_to_ltv_ratio = coerce_float(request.max_cac_to_ltv_ratio, 0.33, minimum=0.0)
        payback_horizon_months = coerce_float(request.payback_horizon_months, 12.0, minimum=0.0)
        expected_monthly_margin_per_customer = coerce_float(request.expected_monthly_margin_per_customer, 0.0, minimum=0.0)

        funnel = self._funnel_model.summarize(request.stages)
        budget = self._budget_optimizer.recommend(
            BudgetOptimizerInputs(
                target_customers=target_customers,
                cost_per_entry=cost_per_entry,
                funnel=funnel,
                setup_cost=setup_cost,
                target_days=target_days,
                available_budget=total_budget,
            )
        )
        timeline = self._timeline_estimator.estimate(
            TimelineEstimatorInputs(
                target_customers=target_customers,
                total_budget=total_budget,
                daily_budget=daily_budget,
                cost_per_entry=cost_per_entry,
                funnel=funnel,
                target_days=target_days,
                setup_cost=setup_cost,
            )
        )
        cac = self._cac_model.evaluate(
            CacInputs(
                total_budget=total_budget,
                acquired_customers=min(target_customers, timeline.affordable_customers),
                gross_margin_ltv=gross_margin_ltv,
                max_cac_to_ltv_ratio=max_cac_to_ltv_ratio,
                payback_horizon_months=payback_horizon_months,
                expected_monthly_margin_per_customer=expected_monthly_margin_per_customer,
                setup_cost=setup_cost,
            )
        )

        customer_gap = max(0, target_customers - timeline.affordable_customers)
        feasible = customer_gap == 0 and budget.budget_gap <= 0.0 and (target_days <= 0.0 or timeline.feasible_in_target_window) and cac.sustainable

        reasons = list(dict.fromkeys((*budget.reasons, *timeline.reasons, *cac.reasons)))
        if target_customers > 0 and funnel.overall_conversion_rate <= 0.0:
            reasons.append("target_unreachable_with_current_funnel")
        if not feasible and not reasons:
            reasons.append("plan_not_feasible")

        score = 1.0
        if target_customers > 0:
            score = min(score, timeline.affordable_customers / target_customers)
        if budget.required_budget > 0.0:
            score = min(score, total_budget / budget.required_budget)
        if target_days > 0.0 and timeline.estimated_days > 0.0 and timeline.estimated_days != float("inf"):
            score = min(score, target_days / timeline.estimated_days)
        if not cac.sustainable:
            score = min(
                score,
                self._policy.sustainability_partial_credit_with_customers
                if timeline.affordable_customers > 0
                else self._policy.sustainability_partial_credit_without_customers,
            )
        score = max(self._policy.score_floor, min(self._policy.score_ceiling, round(score, self._policy.score_precision)))

        summary = "plan is feasible" if feasible else "plan is not feasible"
        return AcquisitionFeasibilityResult(
            feasible=feasible,
            summary=summary,
            reasons=tuple(reasons),
            feasibility_score=score,
            customer_gap=customer_gap,
            budget_gap=budget.budget_gap,
            required_budget=budget.required_budget,
            recommended_daily_budget=budget.recommended_daily_budget,
            estimated_days=timeline.estimated_days,
            funnel=funnel,
            budget=budget,
            timeline=timeline,
            cac=cac,
        )

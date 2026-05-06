from __future__ import annotations

from dataclasses import dataclass

from acquisition import AcquisitionFeasibilityResult

CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION = True


@dataclass(frozen=True, slots=True)
class AcquisitionExplanation:
    status: str
    primary_constraint: str
    budget_gap: float
    customer_gap: int
    estimated_days: float
    required_budget: float
    recommended_daily_budget: float
    achievable_customers: int
    funnel_cycle_days: float
    touchpoints_per_customer: int
    blended_cac: float
    max_sustainable_cac: float
    payback_months: float
    reasons: tuple[str, ...]


def explain_acquisition_result(result: AcquisitionFeasibilityResult) -> AcquisitionExplanation:
    return AcquisitionExplanation(
        status="feasible" if result.feasible else "infeasible",
        primary_constraint=_primary_constraint(result),
        budget_gap=result.budget_gap,
        customer_gap=result.customer_gap,
        estimated_days=result.estimated_days,
        required_budget=result.required_budget,
        recommended_daily_budget=result.recommended_daily_budget,
        achievable_customers=result.timeline.affordable_customers,
        funnel_cycle_days=result.funnel.avg_cycle_days,
        touchpoints_per_customer=result.funnel.touchpoints_per_customer,
        blended_cac=result.cac.blended_cac,
        max_sustainable_cac=result.cac.max_sustainable_cac,
        payback_months=result.cac.payback_months,
        reasons=result.reasons,
    )


def _primary_constraint(result: AcquisitionFeasibilityResult) -> str:
    if result.feasible:
        return result.timeline.constrained_by or "balanced"
    if result.timeline.constrained_by == "funnel_conversion":
        return "funnel_conversion"
    if "cac_above_sustainable_threshold" in result.reasons or "payback_too_slow" in result.reasons:
        return "unit_economics"
    if result.budget_gap > 0.0 or "budget_below_required" in result.reasons:
        return "total_budget"
    if result.timeline.constrained_by == "daily_budget":
        return "daily_budget"
    if result.timeline.constrained_by == "funnel_cycle":
        return "funnel_cycle"
    return result.timeline.constrained_by or "balanced"


__all__ = [
    "AcquisitionExplanation",
    "CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION",
    "explain_acquisition_result",
]

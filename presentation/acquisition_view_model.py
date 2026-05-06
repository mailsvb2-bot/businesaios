from __future__ import annotations

from dataclasses import dataclass

from acquisition import AcquisitionFeasibilityResult
from advisory import (
    AcquisitionRecommendation,
    build_acquisition_recommendations,
    explain_acquisition_result,
    render_acquisition_explanation,
)


CANON_PRESENTATION_ACQUISITION_VIEW_MODEL = True


@dataclass(frozen=True, slots=True)
class AcquisitionRecommendationView:
    kind: str
    priority: int
    title: str
    description: str
    suggested_value: float | int | str
    unit: str


@dataclass(frozen=True, slots=True)
class AcquisitionViewModel:
    status: str
    feasible: bool
    headline: str
    narrative: str
    primary_constraint: str
    budget_gap: float
    customer_gap: int
    estimated_days: float
    achievable_customers: int
    required_budget: float
    recommended_daily_budget: float
    reasons: tuple[str, ...]
    recommendations: tuple[AcquisitionRecommendationView, ...]


def build_acquisition_view_model(result: AcquisitionFeasibilityResult) -> AcquisitionViewModel:
    explanation = explain_acquisition_result(result)
    rendered = render_acquisition_explanation(explanation)
    recommendations = build_acquisition_recommendations(result)
    return AcquisitionViewModel(
        status=explanation.status,
        feasible=bool(result.feasible),
        headline=rendered.headline,
        narrative=rendered.narrative,
        primary_constraint=explanation.primary_constraint,
        budget_gap=float(explanation.budget_gap),
        customer_gap=int(explanation.customer_gap),
        estimated_days=float(explanation.estimated_days),
        achievable_customers=int(explanation.achievable_customers),
        required_budget=float(explanation.required_budget),
        recommended_daily_budget=float(explanation.recommended_daily_budget),
        reasons=tuple(str(item) for item in explanation.reasons),
        recommendations=tuple(_to_recommendation_view(item) for item in recommendations.items),
    )


def _to_recommendation_view(item: AcquisitionRecommendation) -> AcquisitionRecommendationView:
    return AcquisitionRecommendationView(
        kind=item.kind,
        priority=int(item.priority),
        title=item.title,
        description=item.description,
        suggested_value=item.suggested_value,
        unit=item.unit,
    )


__all__ = [
    'AcquisitionRecommendationView',
    'AcquisitionViewModel',
    'CANON_PRESENTATION_ACQUISITION_VIEW_MODEL',
    'build_acquisition_view_model',
]

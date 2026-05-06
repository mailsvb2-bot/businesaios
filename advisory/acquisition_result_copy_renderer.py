from __future__ import annotations

import math
from dataclasses import dataclass

from advisory.acquisition_result_projection import AcquisitionExplanation

CANON_ADVISORY_ACQUISITION_RESULT_COPY_RENDERER = True


@dataclass(frozen=True, slots=True)
class RenderedAcquisitionExplanation:
    headline: str
    narrative: str


def render_acquisition_explanation(
    explanation: AcquisitionExplanation,
) -> RenderedAcquisitionExplanation:
    return RenderedAcquisitionExplanation(
        headline=_headline(explanation),
        narrative=_narrative(explanation),
    )


def _headline(explanation: AcquisitionExplanation) -> str:
    if explanation.status == "feasible":
        return (
            f"План достижим: {explanation.achievable_customers} клиентов "
            f"при бюджете {explanation.required_budget:.2f} и сроке {explanation.estimated_days:.1f} дн."
        )
    if explanation.primary_constraint == "total_budget":
        return f"План недостижим в текущем бюджете: не хватает примерно {explanation.budget_gap:.2f}."
    if explanation.primary_constraint == "daily_budget":
        if math.isfinite(explanation.estimated_days):
            return f"План упирается в дневной темп: реалистичный срок {explanation.estimated_days:.1f} дн."
        return "План упирается в дневной темп: при текущем pace срок не определяется."
    if explanation.primary_constraint == "funnel_cycle":
        return f"План упирается в длину воронки: цикл сделки около {explanation.funnel_cycle_days:.1f} дн."
    if explanation.primary_constraint == "funnel_conversion":
        return "План недостижим из-за нулевой или разрушенной конверсии воронки."
    if explanation.primary_constraint == "unit_economics":
        return "План недостижим по unit economics: CAC/LTV или окупаемость вне допустимых границ."
    return "План недостижим при текущих параметрах."


def _narrative(explanation: AcquisitionExplanation) -> str:
    if explanation.status == "feasible":
        return (
            f"Система оценивает план как реалистичный: требуется бюджет {explanation.required_budget:.2f}, "
            f"рекомендуемый дневной темп {explanation.recommended_daily_budget:.2f}, "
            f"ожидаемый срок {explanation.estimated_days:.1f} дн., "
            f"достижимый объём {explanation.achievable_customers} клиентов."
        )

    parts: list[str] = [
        f"Достижимый объём при текущих параметрах: {explanation.achievable_customers} клиентов."
    ]
    if explanation.customer_gap > 0:
        parts.append(f"До цели не хватает примерно {explanation.customer_gap} клиентов.")
    if explanation.budget_gap > 0.0:
        parts.append(f"Оценочный дефицит бюджета: {explanation.budget_gap:.2f}.")
    if math.isfinite(explanation.estimated_days):
        parts.append(f"Реалистичный срок ближе к {explanation.estimated_days:.1f} дням.")
    else:
        parts.append("При текущем дневном темпе срок не определяется и фактически бесконечен.")

    if explanation.primary_constraint == "unit_economics":
        parts.append(
            f"CAC={explanation.blended_cac:.2f}, допустимый CAC={explanation.max_sustainable_cac:.2f}, "
            f"окупаемость={explanation.payback_months:.1f} мес."
        )
    elif explanation.primary_constraint == "funnel_cycle":
        parts.append(
            f"Суммарная длина воронки около {explanation.funnel_cycle_days:.1f} дней "
            f"при {explanation.touchpoints_per_customer} касаниях."
        )
    elif explanation.primary_constraint == "funnel_conversion":
        parts.append("Верхнеуровневая проблема — воронка не пропускает поток к покупкам.")

    return " ".join(parts)


__all__ = [
    "CANON_ADVISORY_ACQUISITION_RESULT_COPY_RENDERER",
    "RenderedAcquisitionExplanation",
    "render_acquisition_explanation",
]

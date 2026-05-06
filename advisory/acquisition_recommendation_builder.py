from __future__ import annotations

from dataclasses import dataclass

from acquisition import AcquisitionFeasibilityResult
from advisory.acquisition_result_projection import AcquisitionExplanation, explain_acquisition_result

CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER = True


@dataclass(frozen=True, slots=True)
class AcquisitionRecommendation:
    kind: str
    priority: int
    title: str
    description: str
    suggested_value: float | int | str
    unit: str = ""


@dataclass(frozen=True, slots=True)
class AcquisitionRecommendations:
    primary_constraint: str
    items: tuple[AcquisitionRecommendation, ...]


def build_acquisition_recommendations(
    result: AcquisitionFeasibilityResult,
) -> AcquisitionRecommendations:
    explanation = explain_acquisition_result(result)
    items: list[AcquisitionRecommendation] = []

    if result.feasible:
        items.append(
            AcquisitionRecommendation(
                kind="keep_plan",
                priority=1,
                title="План можно запускать",
                description=(
                    "Текущие параметры выглядят реалистично. Сохраняй бюджетный и временной режим, "
                    "а дальше уточняй воронку по факту."
                ),
                suggested_value="keep_current_parameters",
            )
        )
        return AcquisitionRecommendations(
            primary_constraint=explanation.primary_constraint,
            items=tuple(items),
        )

    _append_funnel_recommendations(items, result, explanation)
    _append_budget_recommendations(items, result, explanation)
    _append_time_recommendations(items, result, explanation)
    _append_economics_recommendations(items, result, explanation)

    deduped: list[AcquisitionRecommendation] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(items, key=lambda x: (x.priority, x.kind, x.title)):
        key = (item.kind, item.title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return AcquisitionRecommendations(
        primary_constraint=explanation.primary_constraint,
        items=tuple(deduped),
    )


def _append_budget_recommendations(
    items: list[AcquisitionRecommendation],
    result: AcquisitionFeasibilityResult,
    explanation: AcquisitionExplanation,
) -> None:
    if explanation.primary_constraint != "total_budget":
        return
    items.append(
        AcquisitionRecommendation(
            kind="increase_total_budget",
            priority=1,
            title="Увеличить общий бюджет",
            description=(
                f"Без увеличения общего бюджета план не сойдётся. Один из необходимых шагов — "
                f"закрыть дефицит примерно на {result.budget_gap:.2f}."
            ),
            suggested_value=round(result.required_budget, 2),
            unit="currency",
        )
    )
    if result.recommended_daily_budget > 0.0:
        items.append(
            AcquisitionRecommendation(
                kind="align_daily_budget",
                priority=2,
                title="Подтянуть дневной бюджет к расчётному темпу",
                description=(
                    "Даже при достаточном общем бюджете слишком медленный дневной темп растягивает результат."
                ),
                suggested_value=round(result.recommended_daily_budget, 2),
                unit="currency_per_day",
            )
        )


def _append_time_recommendations(
    items: list[AcquisitionRecommendation],
    result: AcquisitionFeasibilityResult,
    explanation: AcquisitionExplanation,
) -> None:
    if "timeline_exceeds_target_window" not in result.reasons:
        return
    items.append(
        AcquisitionRecommendation(
            kind="extend_timeline",
            priority=1 if explanation.primary_constraint in {"daily_budget", "funnel_cycle"} else 3,
            title="Увеличить допустимый срок",
            description="При текущих параметрах реалистичный срок больше целевого окна.",
            suggested_value=round(result.estimated_days, 1),
            unit="days",
        )
    )


def _append_funnel_recommendations(
    items: list[AcquisitionRecommendation],
    result: AcquisitionFeasibilityResult,
    explanation: AcquisitionExplanation,
) -> None:
    if explanation.primary_constraint == "funnel_conversion":
        items.append(
            AcquisitionRecommendation(
                kind="repair_funnel_conversion",
                priority=1,
                title="Сначала починить конверсию воронки",
                description=(
                    "Пока воронка не пропускает поток к продажам, увеличение бюджета не даст нормального результата."
                ),
                suggested_value="improve_stage_conversion",
            )
        )
        return

    if explanation.primary_constraint == "funnel_cycle":
        items.append(
            AcquisitionRecommendation(
                kind="shorten_funnel_cycle",
                priority=1,
                title="Сократить длину цикла сделки",
                description="Основной ограничитель сейчас — сама длина воронки и количество касаний.",
                suggested_value=round(result.funnel.avg_cycle_days, 1),
                unit="days",
            )
        )
        items.append(
            AcquisitionRecommendation(
                kind="reduce_touchpoints",
                priority=2,
                title="Сократить число касаний до продажи",
                description="Чем меньше обязательных касаний, тем быстрее система доводит клиента до покупки.",
                suggested_value=result.funnel.touchpoints_per_customer,
                unit="touches",
            )
        )


def _append_economics_recommendations(
    items: list[AcquisitionRecommendation],
    result: AcquisitionFeasibilityResult,
    explanation: AcquisitionExplanation,
) -> None:
    if explanation.primary_constraint != "unit_economics":
        return

    if "cac_above_sustainable_threshold" in result.reasons:
        items.append(
            AcquisitionRecommendation(
                kind="reduce_cac",
                priority=1,
                title="Снизить CAC до устойчивого уровня",
                description=(
                    f"Текущий CAC={result.cac.blended_cac:.2f}, а допустимый уровень около "
                    f"{result.cac.max_sustainable_cac:.2f}."
                ),
                suggested_value=round(result.cac.max_sustainable_cac, 2),
                unit="currency",
            )
        )

    if "payback_too_slow" in result.reasons:
        items.append(
            AcquisitionRecommendation(
                kind="speed_up_payback",
                priority=2,
                title="Ускорить окупаемость клиента",
                description="Нужно либо повысить месячную маржу на клиента, либо удешевить привлечение.",
                suggested_value=round(result.cac.payback_months, 1),
                unit="months",
            )
        )


__all__ = [
    "AcquisitionRecommendation",
    "AcquisitionRecommendations",
    "CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER",
    "build_acquisition_recommendations",
]

from __future__ import annotations

from .contracts import AgentBlueprint, AutomationOpportunity, ROIReport


def _money(minor: int | None, currency: str | None) -> dict[str, object] | None:
    if minor is None or not currency:
        return None
    return {"amount_minor": int(minor), "currency": currency}


def opportunity_card(opportunity: AutomationOpportunity) -> dict[str, object]:
    baseline = opportunity.baseline
    return {
        "opportunity_id": opportunity.opportunity_id,
        "process_key": baseline.process_key,
        "eligible": opportunity.eligible,
        "priority_score": opportunity.priority_score,
        "confidence": baseline.confidence,
        "observations": baseline.observation_count,
        "window_days": baseline.window_days,
        "manual_minutes_per_30d": baseline.manual_minutes_per_30d,
        "realized_loss_per_30d": _money(baseline.realized_loss_minor_per_30d, baseline.currency),
        "revenue_at_risk_per_30d": _money(baseline.revenue_at_risk_minor_per_30d, baseline.currency),
        "money_status": baseline.money_status.value,
        "reasons": list(opportunity.reasons),
        "blockers": list(opportunity.blockers),
        "copy": {"headline": "Найдена повторяющаяся потеря времени/денег", "cta": "Подготовить безопасный план автоматизации"},
    }


def blueprint_card(blueprint: AgentBlueprint) -> dict[str, object]:
    return {
        "blueprint_id": blueprint.blueprint_id,
        "process_key": blueprint.process_key,
        "goal": blueprint.owner_goal,
        "initial_stage": blueprint.initial_stage.value,
        "promotion_path": [stage.value for stage in blueprint.promotion_path],
        "expected_coverage": blueprint.expected_coverage,
        "requested_capabilities": list(blueprint.requested_capabilities),
        "forbidden_side_effects": list(blueprint.forbidden_side_effects),
        "executable": blueprint.executable,
        "copy": {
            "headline": "План готов. Сначала — наблюдение без внешних действий",
            "cta": "Передать цель в DecisionCore",
        },
    }


def roi_card(report: ROIReport) -> dict[str, object]:
    return {
        "blueprint_id": report.blueprint_id,
        "intervention_id": report.intervention_id,
        "process_key": report.process_key,
        "evidence_grade": report.evidence_grade.value,
        "comparison_design": report.design.value,
        "manual_minutes_saved_per_30d": report.manual_minutes_saved_per_30d,
        "manual_time_improvement_ratio": report.manual_time_improvement_ratio,
        "gross_savings_per_30d": _money(report.gross_savings_minor_per_30d, report.currency),
        "intervention_cost_per_30d": _money(report.intervention_cost_minor_per_30d, report.currency),
        "net_benefit_per_30d": _money(report.net_benefit_minor_per_30d, report.currency),
        "roi_ratio": report.roi_ratio,
        "causal_claim_allowed": False,
        "caveats": list(report.caveats),
        "copy": {
            "headline": "Что изменилось после подтверждённого вмешательства",
            "causal_note": "Эффект измерен по серверным данным; причинность требует отдельного канонического экспериментального оценщика.",
        },
    }

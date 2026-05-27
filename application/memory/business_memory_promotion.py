from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.memory.business_operating_memory import project_business_memory_governance_summary
from execution.canonical_governance_evidence import canonical_governance_evidence

CANON_BUSINESS_MEMORY_PROMOTION = True


@dataclass(frozen=True)
class ScenarioMemoryAlignment:
    scenario: str
    aligned: bool
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class BusinessMemoryPromotionHelper:
    """Build evidence payloads for governance promotion."""

    def scenario_alignment(
        self,
        *,
        scenario: str | None,
        business_memory_summary: dict[str, Any],
    ) -> ScenarioMemoryAlignment:
        scenario_name = str(scenario or "").strip().lower()
        reasons: list[str] = []
        score = 0.0

        summary = project_business_memory_governance_summary(business_memory_summary)
        active_goals = [str(x).strip().lower() for x in list(summary.get("active_goals") or []) if str(x).strip()]
        learned_preferences = {str(k): str(v) for k, v in dict(summary.get("learned_preferences") or {}).items()}

        if not scenario_name:
            return ScenarioMemoryAlignment(scenario="", aligned=True, score=0.0, reasons=())

        normalized_scenario = scenario_name.replace("_", " ")
        for goal in active_goals:
            if normalized_scenario in goal or goal.replace(" ", "_") == scenario_name:
                score += 0.30
                reasons.append("scenario_matches_active_goal")
                break

        segment = str(learned_preferences.get("segment") or "").strip().lower()
        offer_type = str(learned_preferences.get("offer_type") or "").strip().lower()
        if scenario_name == "lead_processing":
            score += 0.10
            reasons.append("scenario_has_generic_support")
        if scenario_name == "pricing_adjustment" and offer_type:
            score += 0.10
            reasons.append("offer_type_known")
        if scenario_name == "retention_recovery" and segment:
            score += 0.10
            reasons.append("segment_known")

        bounded = max(0.0, min(1.0, float(score)))
        return ScenarioMemoryAlignment(
            scenario=scenario_name,
            aligned=bounded >= 0.10,
            score=bounded,
            reasons=tuple(reasons),
        )

    def build_promotion_evidence(
        self,
        *,
        candidate_record: dict[str, Any],
        business_memory_summary: dict[str, Any],
        fit_report: Any,
        scenario_alignment: Any | None = None,
        baseline_name: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata_payload = dict(metadata or {})
        effective_alignment = scenario_alignment if scenario_alignment is not None else metadata_payload.get('scenario_memory_alignment')
        effective_fit_report = fit_report if fit_report is not None else metadata_payload.get('business_memory_fit')
        governance_evidence = canonical_governance_evidence(
            governance_action='promote_baseline',
            baseline_name=baseline_name,
            candidate_record=candidate_record,
            business_memory_summary=business_memory_summary,
            fit_report=effective_fit_report,
            scenario_alignment=effective_alignment,
            metadata=metadata_payload,
        )
        payload = {
            "business_memory_summary": dict(governance_evidence.get('business_memory_summary') or {}),
            "business_memory_fit": dict(governance_evidence.get('business_memory_fit') or {}),
            "governance_evidence": governance_evidence,
        }
        if scenario_alignment is not None:
            payload["scenario_memory_alignment"] = dict(governance_evidence.get("scenario_memory_alignment") or {})
        return payload


__all__ = [
    "BusinessMemoryPromotionHelper",
    "CANON_BUSINESS_MEMORY_PROMOTION",
    "ScenarioMemoryAlignment",
]

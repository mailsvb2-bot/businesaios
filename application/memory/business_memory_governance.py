from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.memory.business_operating_memory import project_business_memory_governance_summary
from execution.canonical_persistence_vocabulary import canonical_run_persistence_vocabulary

CANON_BUSINESS_MEMORY_GOVERNANCE = True


@dataclass(frozen=True)
class BusinessMemoryFitReport:
    approved: bool
    score: float
    reasons: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class BusinessMemoryGovernanceGate:
    """Evidence-only governance gate.

    It must not issue runtime decisions or unlock effects.
    """

    min_fit_score: float = 0.30

    def evaluate(
        self,
        *,
        candidate_record: dict[str, Any],
        business_memory_summary: dict[str, Any],
    ) -> BusinessMemoryFitReport:
        reasons: list[str] = []
        score = 0.0

        candidate = canonical_run_persistence_vocabulary(candidate_record)
        summary = project_business_memory_governance_summary(business_memory_summary)
        candidate_feedback = dict(candidate.get("final_feedback") or {})
        candidate_goal = str(candidate.get("goal") or "").strip()
        active_goals = [str(x).strip() for x in list(summary.get("active_goals") or []) if str(x).strip()]
        learned_preferences = dict(summary.get("learned_preferences") or {})
        recurring_failures = [str(x).strip() for x in list(summary.get("recurring_failures") or []) if str(x).strip()]
        recurring_wins = [str(x).strip() for x in list(summary.get("recurring_wins") or []) if str(x).strip()]

        if candidate_goal and candidate_goal in active_goals:
            score += 0.20
            reasons.append("goal_matches_active_goal")

        stop_reason = str(candidate.get("stop_reason") or "").strip()
        if stop_reason == "goal_reached":
            score += 0.15
            reasons.append("candidate_goal_reached")

        goal_score = float(candidate_feedback.get("goal_score") or 0.0)
        if goal_score >= 0.80:
            score += 0.20
            reasons.append("candidate_high_goal_score")
        elif goal_score >= 0.50:
            score += 0.10
            reasons.append("candidate_medium_goal_score")

        retry = dict(candidate_feedback.get("retry_classification") or {})
        retry_kind = str(retry.get("kind") or "").strip()
        if retry_kind == "success":
            score += 0.15
            reasons.append("candidate_retry_success")
        elif retry_kind == "operator_required":
            score -= 0.20
            reasons.append("candidate_operator_required")

        error = str(candidate_feedback.get("error") or "").strip()
        if error and error in recurring_failures:
            score -= 0.15
            reasons.append("candidate_repeats_failure")

        if bool(candidate_feedback.get("goal_reached")) and "goal_reached" in recurring_wins:
            score += 0.10
            reasons.append("candidate_repeats_known_win")

        region_pref = str(learned_preferences.get("region") or "").strip()
        channel_pref = str(learned_preferences.get("channel") or "").strip()
        candidate_region = str(candidate.get("region") or "").strip()
        candidate_channel = str(candidate.get("channel") or "").strip()

        if region_pref and candidate_region and region_pref == candidate_region:
            score += 0.05
            reasons.append("region_matches_preference")
        if channel_pref and candidate_channel and channel_pref == candidate_channel:
            score += 0.05
            reasons.append("channel_matches_preference")

        bounded = max(0.0, min(1.0, float(score)))
        approved = bounded >= float(self.min_fit_score)
        summary = f"business_memory_fit={bounded:.3f}; approved={approved}; reasons={','.join(reasons)}"
        return BusinessMemoryFitReport(approved=approved, score=bounded, reasons=tuple(reasons), summary=summary)


__all__ = [
    "BusinessMemoryFitReport",
    "BusinessMemoryGovernanceGate",
    "CANON_BUSINESS_MEMORY_GOVERNANCE",
]

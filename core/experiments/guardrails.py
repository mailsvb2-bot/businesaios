from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from config.live_canary_policy import LiveCanaryPolicy
from core.experiments.statistics import LiveCanaryStatistics, summarize


class CanaryDecision(str, Enum):
    CONTINUE = "continue"
    ROLLBACK = "rollback"
    PROMOTE = "promote"


@dataclass(frozen=True)
class GuardrailResult:
    decision: CanaryDecision
    reasons: tuple[str, ...]
    metrics: dict[str, object]
    statistics: LiveCanaryStatistics | None = None

    @property
    def promotable(self) -> bool:
        return self.decision is CanaryDecision.PROMOTE


def _finite_metrics(metrics: dict[str, object]) -> bool:
    for value in metrics.values():
        if isinstance(value, float) and not math.isfinite(value):
            return False
    return True


class LiveCanaryGuard:
    @staticmethod
    def evaluate(
        metrics: dict[str, object],
        policy: LiveCanaryPolicy,
    ) -> GuardrailResult:
        policy.assert_valid()
        if not _finite_metrics(metrics):
            return GuardrailResult(
                CanaryDecision.ROLLBACK,
                ("non_finite_metric",),
                dict(metrics),
            )

        stats = summarize(metrics, policy.candidate_fraction)
        immediate: list[str] = []
        if (
            int(metrics.get("critical_violations", 0) or 0)
            > policy.max_critical_violations
        ):
            immediate.append("critical_violation")
        if stats.candidate.error_rate > policy.max_error_rate:
            immediate.append("candidate_error_rate")
        if stats.candidate.complaint_rate > policy.max_complaint_rate:
            immediate.append("candidate_complaint_rate")
        if (
            float(metrics.get("candidate_cost_24h", 0.0) or 0.0)
            > policy.max_daily_cost
        ):
            immediate.append("candidate_cost_budget")
        if (
            int(metrics.get("candidate_actions_24h", 0) or 0)
            > policy.max_candidate_actions_per_day
        ):
            immediate.append("candidate_action_frequency")
        if (
            int(
                metrics.get(
                    "candidate_max_actions_per_subject_24h",
                    0,
                )
                or 0
            )
            > policy.max_candidate_actions_per_subject_24h
        ):
            immediate.append("candidate_subject_frequency")
        if (
            int(metrics.get("assignment_count", 0) or 0)
            >= policy.min_assignments
            and abs(stats.sample_ratio_z) > policy.max_sample_ratio_z
        ):
            immediate.append("sample_ratio_mismatch")
        if immediate:
            return GuardrailResult(
                CanaryDecision.ROLLBACK,
                tuple(immediate),
                dict(metrics),
                stats,
            )

        enough_data = all(
            (
                int(
                    metrics.get(
                        "mature_assignment_count",
                        metrics.get("assignment_count", 0),
                    )
                    or 0
                )
                >= policy.min_assignments,
                stats.candidate.assignments >= policy.min_candidate_assignments,
                stats.control.outcomes >= policy.min_outcomes_per_arm,
                stats.candidate.outcomes >= policy.min_outcomes_per_arm,
                float(metrics.get("duration_seconds", 0.0) or 0.0)
                >= policy.min_duration_seconds,
            )
        )
        if not enough_data:
            return GuardrailResult(
                CanaryDecision.CONTINUE,
                ("insufficient_mature_evidence",),
                dict(metrics),
                stats,
            )

        control_rate = stats.control.conversion_rate
        allowed_drop = policy.max_relative_conversion_drop * max(
            control_rate,
            1e-9,
        )
        quality_reasons: list[str] = []
        if stats.conversion_difference_lower_bound < -allowed_drop:
            quality_reasons.append("conversion_noninferiority_failed")
        if (
            stats.control.cost_per_outcome > 0
            and stats.candidate.cost_per_outcome
            > stats.control.cost_per_outcome * policy.max_cost_per_outcome_ratio
        ):
            quality_reasons.append("cost_per_outcome_regressed")
        if quality_reasons:
            return GuardrailResult(
                CanaryDecision.ROLLBACK,
                tuple(quality_reasons),
                dict(metrics),
                stats,
            )

        return GuardrailResult(
            CanaryDecision.PROMOTE,
            ("business_outcome_noninferiority_proven",),
            dict(metrics),
            stats,
        )


__all__ = ["CanaryDecision", "GuardrailResult", "LiveCanaryGuard"]

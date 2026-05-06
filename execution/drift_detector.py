from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_HEADLESS_DRIFT_DETECTOR = True


@dataclass(frozen=True)
class DriftReport:
    severity: str
    goal_score_delta: float
    completion_changed: bool
    stop_reason_changed: bool
    retry_kind_changed: bool
    summary: str


@dataclass(frozen=True)
class DriftDetector:
    """
    Detects meaningful drift between a promoted baseline and a candidate run.

    Analysis only. Never affects execution.
    """

    low_threshold: float = 0.05
    medium_threshold: float = 0.15

    def detect(self, *, baseline: dict[str, Any], candidate: dict[str, Any]) -> DriftReport:
        baseline_record = dict(baseline.get("record") or baseline)
        candidate_record = dict(candidate)

        base_feedback = dict(baseline_record.get("final_feedback") or {})
        cand_feedback = dict(candidate_record.get("final_feedback") or {})

        base_score = self._safe_float(base_feedback.get("goal_score"))
        cand_score = self._safe_float(cand_feedback.get("goal_score"))
        delta = float(cand_score) - float(base_score)

        completion_changed = bool(baseline_record.get("completed")) != bool(candidate_record.get("completed"))
        stop_reason_changed = str(baseline_record.get("stop_reason") or "") != str(candidate_record.get("stop_reason") or "")
        retry_kind_changed = self._retry_kind(base_feedback) != self._retry_kind(cand_feedback)

        severity = self._severity(
            delta=delta,
            completion_changed=completion_changed,
            stop_reason_changed=stop_reason_changed,
            retry_kind_changed=retry_kind_changed,
        )

        summary = (
            f"drift={severity}; goal_score_delta={delta:.3f}; "
            f"completion_changed={completion_changed}; "
            f"stop_reason_changed={stop_reason_changed}; "
            f"retry_kind_changed={retry_kind_changed}"
        )

        return DriftReport(
            severity=severity,
            goal_score_delta=float(delta),
            completion_changed=completion_changed,
            stop_reason_changed=stop_reason_changed,
            retry_kind_changed=retry_kind_changed,
            summary=summary,
        )

    def _severity(
        self,
        *,
        delta: float,
        completion_changed: bool,
        stop_reason_changed: bool,
        retry_kind_changed: bool,
    ) -> str:
        abs_delta = abs(float(delta))
        if completion_changed:
            return "high"
        if stop_reason_changed and retry_kind_changed:
            return "high"
        if abs_delta >= float(self.medium_threshold):
            return "medium"
        if stop_reason_changed or retry_kind_changed or abs_delta >= float(self.low_threshold):
            return "low"
        return "none"

    @staticmethod
    def _retry_kind(feedback: dict[str, Any]) -> str:
        retry = feedback.get("retry_classification")
        if isinstance(retry, dict):
            return str(retry.get("kind") or "")
        return ""

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0


__all__ = [
    "CANON_HEADLESS_DRIFT_DETECTOR",
    "DriftDetector",
    "DriftReport",
]

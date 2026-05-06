from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CANON_HEADLESS_DRIFT_AUDIT_REPORT = True


@dataclass(frozen=True)
class DriftAuditReportBuilder:
    """
    Builds a human-readable audit report for baseline-vs-candidate drift.

    Reporting only. Never affects execution.
    """

    def build(
        self,
        *,
        baseline_name: str,
        baseline: dict[str, Any],
        candidate: dict[str, Any],
        drift: Any,
        diff: Any,
    ) -> str:
        baseline_record = dict(baseline.get("record") or baseline)
        lines = [
            f"Baseline: {baseline_name}",
            f"Baseline run: {baseline_record.get('run_id')}",
            f"Candidate run: {candidate.get('run_id')}",
            f"Drift severity: {getattr(drift, 'severity', 'unknown')}",
            f"Goal score delta: {getattr(drift, 'goal_score_delta', 0.0):.3f}",
            f"Completion changed: {bool(getattr(drift, 'completion_changed', False))}",
            f"Stop reason changed: {bool(getattr(drift, 'stop_reason_changed', False))}",
            f"Retry kind changed: {bool(getattr(drift, 'retry_kind_changed', False))}",
            f"Changed fields: {', '.join(getattr(diff, 'changed_fields', ()))}",
            f"Left-only events: {', '.join(getattr(diff, 'left_only_events', ()))}",
            f"Right-only events: {', '.join(getattr(diff, 'right_only_events', ()))}",
        ]
        return "\n".join(lines)


__all__ = [
    "CANON_HEADLESS_DRIFT_AUDIT_REPORT",
    "DriftAuditReportBuilder",
]

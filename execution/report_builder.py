from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from execution.canonical_run_artifacts import canonical_report_builder_input


CANON_HEADLESS_REPORT_BUILDER = True


@dataclass(frozen=True)
class ReportBuilder:
    """
    Builds a compact human-readable report for a headless run.
    """

    def build(self, *, record: dict[str, Any]) -> str:
        normalized_record = canonical_report_builder_input(record)
        feedback = dict(normalized_record.get("final_feedback") or {})
        execution_feedback = dict(normalized_record.get("execution_feedback") or {})
        lines = [
            f"Run: {normalized_record.get('run_id')}",
            f"Goal: {normalized_record.get('goal')}",
            f"Business: {normalized_record.get('business_id')}",
            f"Tenant: {normalized_record.get('tenant_id')}",
            f"Completed: {bool(normalized_record.get('completed'))}",
            f"Stop reason: {normalized_record.get('stop_reason')}",
            f"Steps: {int(normalized_record.get('steps_count') or 0)}",
            f"Verification status: {normalized_record.get('verification_status') or execution_feedback.get('verification_status') or 'unknown'}",
            (
                "Execution semantics: "
                f"attempted={bool(execution_feedback.get('attempted', feedback.get('attempted')))}, "
                f"executed={bool(execution_feedback.get('executed', feedback.get('executed')))}, "
                f"verified={bool(execution_feedback.get('verified', feedback.get('verified')))}, "
                f"operator_required={bool(execution_feedback.get('operator_required', feedback.get('operator_required')))}"
            ),
            f"Goal score: {self._safe_float(feedback.get('goal_score')):.3f}",
        ]

        retry = feedback.get("retry_classification")
        if isinstance(retry, dict):
            lines.append(
                "Retry classification: "
                f"{retry.get('kind')} (should_retry={bool(retry.get('should_retry'))})"
            )

        explanation = feedback.get("policy_explanation")
        if isinstance(explanation, dict):
            lines.append(f"Policy: {explanation.get('policy_id')} — {explanation.get('summary')}")

        reasons = feedback.get("goal_score_reasons")
        if isinstance(reasons, list) and reasons:
            lines.append("Reasons: " + ", ".join(str(x) for x in reasons))

        return "\n".join(lines)

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0


__all__ = [
    "CANON_HEADLESS_REPORT_BUILDER",
    "ReportBuilder",
]

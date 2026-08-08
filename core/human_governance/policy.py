from __future__ import annotations

import math
from dataclasses import replace

from .enums import ReviewStatus, RiskLevel, SalesHandoffReason
from .errors import InvalidActorError, InvalidReasonError, ReviewAlreadyClosedError
from .types import ApprovalDecision, OverrideRecord


class HumanGovernancePolicy:
    """
    Единая точка правил, чтобы статусы и переходы
    не расползались по service / repositories / evaluators / writers.
    """

    TERMINAL_STATUSES = frozenset(
        {
            ReviewStatus.APPROVED.value,
            ReviewStatus.REJECTED.value,
            ReviewStatus.CLOSED.value,
        }
    )

    OPEN_QUEUE_STATUSES = frozenset(
        {
            ReviewStatus.REQUESTED.value,
            ReviewStatus.PAUSED.value,
            ReviewStatus.ESCALATED.value,
        }
    )

    APPROVAL_PENDING_STATUSES = frozenset(
        {
            ReviewStatus.REQUESTED.value,
            ReviewStatus.PAUSED.value,
            ReviewStatus.ESCALATED.value,
        }
    )

    SALES_MIN_AUTOMATION_CONFIDENCE = 0.72
    SALES_FAILURE_HANDOFF_THRESHOLD = 2

    def is_terminal(self, status: str) -> bool:
        return status in self.TERMINAL_STATUSES

    def is_open_queue_status(self, status: str) -> bool:
        return status in self.OPEN_QUEUE_STATUSES

    def needs_approval(self, status: str) -> bool:
        return status in self.APPROVAL_PENDING_STATUSES

    def ensure_actionable(self, status: str) -> None:
        if self.is_terminal(status):
            raise ReviewAlreadyClosedError(f"review already terminal: status='{status}'")

    def validate_actor_id(self, actor_id: str) -> str:
        value = actor_id.strip()
        if not value:
            raise InvalidActorError("actor_id must not be empty")
        return value

    def validate_reason(self, reason: str) -> str:
        value = reason.strip()
        if not value:
            raise InvalidReasonError("reason must not be empty")
        return value

    def validate_approval_decision(self, decision: ApprovalDecision) -> ApprovalDecision:
        actor_id = self.validate_actor_id(decision.actor_id)
        rationale = self.validate_reason(decision.rationale)
        return replace(
            decision,
            actor_id=actor_id,
            rationale=rationale,
        )

    def validate_override_record(self, record: OverrideRecord) -> OverrideRecord:
        actor_id = self.validate_actor_id(record.actor_id)
        reason = self.validate_reason(record.reason)
        scope = record.scope.strip() or "review"
        return replace(
            record,
            actor_id=actor_id,
            reason=reason,
            scope=scope,
        )

    def evaluate_sales_handoff(
        self,
        *,
        model_confidence: float,
        explicit_human_request: bool,
        sensitive_context: bool,
        pricing_exception: bool,
        negative_sentiment: bool,
        failed_attempts: int,
        subject_closed: bool,
    ) -> tuple[SalesHandoffReason, RiskLevel, str] | None:
        """Return a review classification only; never an action or effect."""

        flags = {
            "explicit_human_request": explicit_human_request,
            "sensitive_context": sensitive_context,
            "pricing_exception": pricing_exception,
            "negative_sentiment": negative_sentiment,
            "subject_closed": subject_closed,
        }
        for name, value in flags.items():
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a boolean")
        if isinstance(failed_attempts, bool) or not isinstance(failed_attempts, int):
            raise ValueError("failed_attempts must be a non-negative integer")
        if failed_attempts < 0:
            raise ValueError("failed_attempts must be a non-negative integer")
        try:
            confidence = float(model_confidence)
        except (TypeError, ValueError) as exc:
            raise ValueError("model_confidence must be finite") from exc
        if not math.isfinite(confidence):
            raise ValueError("model_confidence must be finite")
        confidence = max(0.0, min(confidence, 1.0))

        if sensitive_context:
            return (
                SalesHandoffReason.SENSITIVE_CONTEXT,
                RiskLevel.CRITICAL,
                "Sensitive or regulated context requires human review.",
            )
        if explicit_human_request:
            return (
                SalesHandoffReason.EXPLICIT_REQUEST,
                RiskLevel.HIGH,
                "The customer explicitly requested a human.",
            )
        if subject_closed:
            return None
        if pricing_exception:
            return (
                SalesHandoffReason.PRICING_EXCEPTION,
                RiskLevel.HIGH,
                "The opportunity is outside the approved pricing or offer path.",
            )
        if failed_attempts >= self.SALES_FAILURE_HANDOFF_THRESHOLD:
            return (
                SalesHandoffReason.REPEATED_FAILURE,
                RiskLevel.HIGH,
                "Repeated automation failure requires human review.",
            )
        if negative_sentiment:
            return (
                SalesHandoffReason.NEGATIVE_SENTIMENT,
                RiskLevel.MEDIUM,
                "Negative sentiment warrants human review.",
            )
        if confidence < self.SALES_MIN_AUTOMATION_CONFIDENCE:
            return (
                SalesHandoffReason.LOW_CONFIDENCE,
                RiskLevel.MEDIUM,
                "Model confidence is below the approved automation threshold.",
            )
        return None

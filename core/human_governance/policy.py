from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from .enums import ReviewStatus, RiskLevel
from .errors import InvalidActorError, InvalidReasonError, ReviewAlreadyClosedError
from .types import ApprovalDecision, OverrideRecord


class HumanGovernancePolicy:
    """Canonical human review/override policy; never a decision issuer."""

    TERMINAL_STATUSES = frozenset({ReviewStatus.APPROVED.value, ReviewStatus.REJECTED.value, ReviewStatus.CLOSED.value})
    OPEN_QUEUE_STATUSES = frozenset({ReviewStatus.REQUESTED.value, ReviewStatus.PAUSED.value, ReviewStatus.ESCALATED.value})
    APPROVAL_PENDING_STATUSES = OPEN_QUEUE_STATUSES
    SALES_MIN_AUTOMATION_CONFIDENCE = 0.72
    SALES_FAILURE_HANDOFF_THRESHOLD = 2
    SALES_HANDOFF_CONTEXT_BYTES = 32 * 1024

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
        return replace(decision, actor_id=self.validate_actor_id(decision.actor_id), rationale=self.validate_reason(decision.rationale))

    def validate_override_record(self, record: OverrideRecord) -> OverrideRecord:
        return replace(record, actor_id=self.validate_actor_id(record.actor_id), reason=self.validate_reason(record.reason), scope=record.scope.strip() or "review")

    def evaluate_sales_handoff(
        self,
        *,
        tenant_id: str,
        subject_id: str,
        model_confidence: float,
        explicit_human_request: bool = False,
        sensitive_context: bool = False,
        pricing_exception: bool = False,
        negative_sentiment: bool = False,
        failed_attempts: int = 0,
        subject_closed: bool = False,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, object] | None:
        flags = (explicit_human_request, sensitive_context, pricing_exception, negative_sentiment, subject_closed)
        if not str(tenant_id).strip() or not str(subject_id).strip():
            raise ValueError("tenant_id and subject_id are required")
        if any(not isinstance(value, bool) for value in flags):
            raise ValueError("handoff flags must be booleans")
        if isinstance(failed_attempts, bool) or not isinstance(failed_attempts, int) or failed_attempts < 0:
            raise ValueError("failed_attempts must be a non-negative integer")
        try:
            confidence = float(model_confidence)
        except (TypeError, ValueError) as exc:
            raise ValueError("model_confidence must be finite") from exc
        if not math.isfinite(confidence):
            raise ValueError("model_confidence must be finite")
        candidates = (
            (sensitive_context, "sensitive_context", RiskLevel.CRITICAL, "Sensitive or regulated context requires human review."),
            (explicit_human_request, "explicit_request", RiskLevel.HIGH, "The customer explicitly requested a human."),
            (not subject_closed and pricing_exception, "pricing_exception", RiskLevel.HIGH, "The opportunity is outside the approved pricing or offer path."),
            (not subject_closed and failed_attempts >= self.SALES_FAILURE_HANDOFF_THRESHOLD, "repeated_failure", RiskLevel.HIGH, "Repeated automation failure requires human review."),
            (not subject_closed and negative_sentiment, "negative_sentiment", RiskLevel.MEDIUM, "Negative sentiment warrants human review."),
            (not subject_closed and confidence < self.SALES_MIN_AUTOMATION_CONFIDENCE, "low_confidence", RiskLevel.MEDIUM, "Model confidence is below the approved automation threshold."),
        )
        selected = next((row for row in candidates if row[0]), None)
        if selected is None:
            return None
        payload_context = dict(context or {})
        try:
            encoded = json.dumps(payload_context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("handoff context must be JSON serializable") from exc
        if len(encoded.encode("utf-8")) > self.SALES_HANDOFF_CONTEXT_BYTES:
            raise ValueError("handoff context is too large")
        _, reason, risk, summary = selected
        return {"tenant_id": str(tenant_id).strip(), "subject_id": str(subject_id).strip(), "operator_required": True,
                "reason": reason, "risk_level": risk.value, "summary": summary, "context": payload_context,
                "decision_authority": False, "effect_authority": False}

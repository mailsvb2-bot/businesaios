from __future__ import annotations

from dataclasses import replace

from .enums import ReviewStatus
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

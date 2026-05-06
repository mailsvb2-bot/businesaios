from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from execution.verification.verification_contract import VerificationDecision, VerificationPolicy, VerificationRequest
from execution.verification.verification_timeout_policy import VerificationTimeoutState
CANON_DELAYED_VERIFICATION_RETRY = True
def _utc_now() -> datetime:
    return datetime.now(UTC)
@dataclass(frozen=True, slots=True)
class VerificationRetryPlan:
    should_retry: bool
    retry_at: datetime | None
    retry_reason: str
    attempt_index: int
    next_attempt_index: int
    terminal: bool
    def to_dict(self) -> dict[str, object]:
        return {
            "should_retry": self.should_retry,
            "retry_at": None if self.retry_at is None else self.retry_at.isoformat(),
            "retry_reason": self.retry_reason,
            "attempt_index": self.attempt_index,
            "next_attempt_index": self.next_attempt_index,
            "terminal": self.terminal,
        }
class DelayedVerificationRetry:
    def plan(
        self,
        *,
        request: VerificationRequest,
        policy: VerificationPolicy,
        decision: VerificationDecision,
        timeout_state: VerificationTimeoutState,
        attempt_index: int,
        now: datetime | None = None,
    ) -> VerificationRetryPlan:
        current = now or _utc_now()
        if decision.verified:
            return VerificationRetryPlan(False, None, "already_verified", attempt_index, attempt_index, True)
        if timeout_state.expired:
            return VerificationRetryPlan(False, None, "verification_timeout_expired", attempt_index, attempt_index, True)
        if not policy.allow_delayed_verification:
            return VerificationRetryPlan(False, None, "delayed_verification_disabled", attempt_index, attempt_index, True)
        if not decision.retryable:
            return VerificationRetryPlan(False, None, "decision_not_retryable", attempt_index, attempt_index, True)
        if attempt_index >= len(policy.retry_backoff_seconds):
            return VerificationRetryPlan(False, None, "retry_budget_exhausted", attempt_index, attempt_index, True)
        delay = int(policy.retry_backoff_seconds[attempt_index])
        retry_at = current + timedelta(seconds=max(1, delay))
        deadline = timeout_state.deadline
        if retry_at >= deadline:
            return VerificationRetryPlan(False, None, "retry_would_cross_deadline", attempt_index, attempt_index, True)
        if request.action_id == "":
            return VerificationRetryPlan(False, None, "missing_action_id", attempt_index, attempt_index, True)
        return VerificationRetryPlan(True, retry_at, decision.reason, attempt_index, attempt_index + 1, False)
__all__ = ["CANON_DELAYED_VERIFICATION_RETRY", "VerificationRetryPlan", "DelayedVerificationRetry"]

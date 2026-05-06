from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from execution.verification.verification_contract import VerificationPolicy, VerificationRequest
CANON_VERIFICATION_TIMEOUT_POLICY = True
def _utc_now() -> datetime:
    return datetime.now(UTC)
@dataclass(frozen=True, slots=True)
class VerificationTimeoutState:
    deadline: datetime
    expired: bool
    remaining_seconds: int
    age_seconds: int
    def to_dict(self) -> dict[str, object]:
        return {
            "deadline": self.deadline.isoformat(),
            "expired": self.expired,
            "remaining_seconds": self.remaining_seconds,
            "age_seconds": self.age_seconds,
        }
class VerificationTimeoutPolicy:
    def deadline_for(self, *, request: VerificationRequest, policy: VerificationPolicy) -> datetime:
        if request.verification_deadline is not None:
            return request.verification_deadline
        return request.requested_at + timedelta(seconds=max(1, int(policy.timeout_seconds)))
    def evaluate(self, *, request: VerificationRequest, policy: VerificationPolicy, now: datetime | None = None) -> VerificationTimeoutState:
        current = now or _utc_now()
        deadline = self.deadline_for(request=request, policy=policy)
        remaining = int((deadline - current).total_seconds())
        age = int((current - request.requested_at).total_seconds())
        return VerificationTimeoutState(deadline=deadline, expired=remaining <= 0, remaining_seconds=max(0, remaining), age_seconds=max(0, age))
__all__ = ["CANON_VERIFICATION_TIMEOUT_POLICY", "VerificationTimeoutState", "VerificationTimeoutPolicy"]

from __future__ import annotations

from dataclasses import replace

from ..contracts import HumanGovernancePolicyContract, ReviewRepository
from ..enums import ReviewStatus
from ..errors import ReviewNotFoundError
from ..types import ApprovalDecision, ApprovalState, utc_now


class RejectionWriterImpl:
    def __init__(
        self,
        review_repository: ReviewRepository,
        policy: HumanGovernancePolicyContract,
    ) -> None:
        self._review_repository = review_repository
        self._policy = policy

    def write_rejection(self, decision: ApprovalDecision) -> ApprovalState:
        decision = self._policy.validate_approval_decision(decision)

        current = self._review_repository.get(decision.review_id)
        if current is None:
            raise ReviewNotFoundError(f"review '{decision.review_id}' not found")

        self._policy.ensure_actionable(current.status)
        updated_at = utc_now()

        updated = replace(
            current,
            status=ReviewStatus.REJECTED.value,
            metadata={
                **dict(current.metadata),
                "decided_by": decision.actor_id,
                "decided_at": decision.decided_at,
                "decision_reason": decision.rationale,
            },
            updated_at=updated_at,
        )
        self._review_repository.upsert(updated)

        return ApprovalState(
            review_id=updated.review_id,
            status=updated.status,
            decided_by=decision.actor_id,
            decided_at=decision.decided_at,
            reason=decision.rationale,
        )

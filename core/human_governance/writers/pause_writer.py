from __future__ import annotations

from dataclasses import replace

from ..contracts import HumanGovernancePolicyContract, ReviewRepository
from ..enums import ReviewStatus
from ..errors import ReviewNotFoundError
from ..types import ApprovalState, utc_now


class PauseWriterImpl:
    def __init__(
        self,
        review_repository: ReviewRepository,
        policy: HumanGovernancePolicyContract,
    ) -> None:
        self._review_repository = review_repository
        self._policy = policy

    def write_pause(self, review_id: str, reason: str, actor_id: str) -> ApprovalState:
        normalized_actor_id = self._policy.validate_actor_id(actor_id)
        normalized_reason = self._policy.validate_reason(reason)

        review = self._review_repository.get(review_id)
        if review is None:
            raise ReviewNotFoundError(f"review '{review_id}' not found")

        self._policy.ensure_actionable(review.status)

        now = utc_now()
        updated = replace(
            review,
            status=ReviewStatus.PAUSED.value,
            metadata={
                **dict(review.metadata),
                "paused_by": normalized_actor_id,
                "paused_at": now,
                "pause_reason": normalized_reason,
            },
            updated_at=now,
        )
        self._review_repository.upsert(updated)

        return ApprovalState(
            review_id=review_id,
            status=updated.status,
            decided_by=normalized_actor_id,
            decided_at=now,
            reason=normalized_reason,
        )

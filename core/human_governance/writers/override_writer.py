from __future__ import annotations

from dataclasses import replace

from ..contracts import HumanGovernancePolicyContract, OverrideRepository, ReviewRepository
from ..enums import ReviewStatus
from ..errors import DuplicateOverrideError, ReviewNotFoundError
from ..types import OverrideRecord, utc_now


class OverrideWriterImpl:
    """
    Override не принимает решений.
    Он не является вторым approval-engine.

    Он только:
    - сохраняет факт override;
    - переводит review в approved;
    - оставляет trace в metadata.

    Вся допустимость override проверяется выше:
    - service
    - policy
    - unauthorized_override_guard
    """

    def __init__(
        self,
        review_repository: ReviewRepository,
        override_repository: OverrideRepository,
        policy: HumanGovernancePolicyContract,
    ) -> None:
        self._review_repository = review_repository
        self._override_repository = override_repository
        self._policy = policy

    def write_override(self, record: OverrideRecord) -> OverrideRecord:
        record = self._policy.validate_override_record(record)

        if self._override_repository.get(record.override_id) is not None:
            raise DuplicateOverrideError(
                f"override '{record.override_id}' already exists"
            )

        review = self._review_repository.get(record.review_id)
        if review is None:
            raise ReviewNotFoundError(f"review '{record.review_id}' not found")

        self._policy.ensure_actionable(review.status)
        self._override_repository.add(record)

        updated = replace(
            review,
            status=ReviewStatus.APPROVED.value,
            metadata={
                **dict(review.metadata),
                "override_applied": True,
                "override_by": record.actor_id,
                "override_reason": record.reason,
                "override_at": record.created_at,
                "override_scope": record.scope,
            },
            updated_at=utc_now(),
        )
        self._review_repository.upsert(updated)
        return record

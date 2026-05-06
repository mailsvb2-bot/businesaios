from __future__ import annotations

from typing import Sequence

from ..contracts import HumanGovernancePolicyContract, ReviewRepository
from ..types import ReviewItem


class ReviewQueueReaderImpl:
    def __init__(
        self,
        review_repository: ReviewRepository,
        policy: HumanGovernancePolicyContract,
    ) -> None:
        self._review_repository = review_repository
        self._policy = policy

    def read_queue(self, limit: int = 100) -> Sequence[ReviewItem]:
        items = self._review_repository.list_open(limit=limit)
        return [item for item in items if self._policy.is_open_queue_status(item.status)]

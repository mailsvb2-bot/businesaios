from __future__ import annotations

from typing import Sequence

from ..contracts import HumanGovernancePolicyContract
from ..types import ReviewItem


class InMemoryReviewRepository:
    """
    Репозиторий не решает бизнес-логику.
    Только хранит и отдаёт.
    Фильтр open-status использует policy, чтобы не дублировать статусные правила.
    """

    def __init__(self, policy: HumanGovernancePolicyContract) -> None:
        self._policy = policy
        self._items: dict[str, ReviewItem] = {}

    def get(self, review_id: str) -> ReviewItem | None:
        return self._items.get(review_id)

    def upsert(self, item: ReviewItem) -> ReviewItem:
        self._items[item.review_id] = item
        return item

    def list_open(self, limit: int = 100) -> Sequence[ReviewItem]:
        items = [
            item
            for item in self._items.values()
            if self._policy.is_open_queue_status(item.status)
        ]
        items.sort(key=lambda item: (item.requested_at, item.review_id))
        return items[:limit]

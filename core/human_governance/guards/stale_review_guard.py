from __future__ import annotations

from datetime import timedelta

from ..errors import StaleReviewError
from ..types import ReviewItem, to_aware_utc, utc_now


class StaleReviewGuard:
    def __init__(self, max_age_hours: int = 48) -> None:
        self._max_age = timedelta(hours=max_age_hours)

    def ensure_fresh(self, review: ReviewItem) -> None:
        requested_at = to_aware_utc(review.requested_at)
        age = utc_now() - requested_at
        if age > self._max_age:
            raise StaleReviewError(
                f"review '{review.review_id}' is stale: age='{age}' max_age='{self._max_age}'"
            )

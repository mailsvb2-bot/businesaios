from __future__ import annotations

from typing import Sequence

from ..types import ReviewItem


class ReviewQueueProjection:
    def project(self, items: Sequence[ReviewItem]) -> list[dict[str, object]]:
        return [
            {
                "review_id": item.review_id,
                "decision_id": item.decision_id,
                "subject_type": item.subject_type,
                "subject_id": item.subject_id,
                "risk_level": item.risk_level,
                "status": item.status,
                "requested_by": item.requested_by,
                "requested_at": item.requested_at.isoformat(),
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in items
        ]

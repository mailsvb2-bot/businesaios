from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from ..contracts import ReviewRepository
from ..types import ApprovalState


def _read_first_str(metadata: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _read_first_datetime(metadata: Mapping[str, Any], *keys: str) -> datetime | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, datetime):
            return value
    return None


class ApprovalStateReaderImpl:
    """
    Читает state из review.
    Не вычисляет ничего "умного".
    Только аккуратно нормализует известные metadata-следы:
    - decision_*
    - pause_*
    - override_*
    """

    def __init__(self, review_repository: ReviewRepository) -> None:
        self._review_repository = review_repository

    def read_state(self, review_id: str) -> ApprovalState | None:
        item = self._review_repository.get(review_id)
        if item is None:
            return None

        metadata = item.metadata

        decided_by = _read_first_str(
            metadata,
            "decided_by",
            "paused_by",
            "override_by",
        )
        decided_at = _read_first_datetime(
            metadata,
            "decided_at",
            "paused_at",
            "override_at",
        )
        reason = _read_first_str(
            metadata,
            "decision_reason",
            "pause_reason",
            "override_reason",
        )

        return ApprovalState(
            review_id=item.review_id,
            status=item.status,
            decided_by=decided_by,
            decided_at=decided_at,
            reason=reason,
        )

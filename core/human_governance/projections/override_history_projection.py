from __future__ import annotations

from typing import Sequence

from ..types import OverrideRecord


class OverrideHistoryProjection:
    def project(self, items: Sequence[OverrideRecord]) -> list[dict[str, object]]:
        return [
            {
                "override_id": item.override_id,
                "review_id": item.review_id,
                "actor_id": item.actor_id,
                "reason": item.reason,
                "scope": item.scope,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]

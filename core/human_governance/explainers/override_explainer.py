from __future__ import annotations

from ..types import OverrideRecord


class OverrideExplainer:
    def explain(self, record: OverrideRecord) -> dict[str, object]:
        return {
            "override_id": record.override_id,
            "review_id": record.review_id,
            "actor_id": record.actor_id,
            "reason": record.reason,
            "scope": record.scope,
            "created_at": record.created_at.isoformat(),
        }

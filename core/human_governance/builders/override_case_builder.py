from __future__ import annotations

from ..contracts import OverrideRepository


class OverrideCaseBuilder:
    def __init__(self, override_repository: OverrideRepository) -> None:
        self._override_repository = override_repository

    def build(self, review_id: str) -> dict[str, object]:
        history = list(self._override_repository.list_for_review(review_id))
        latest_override = history[-1] if history else None

        return {
            "review_id": review_id,
            "override_count": len(history),
            "latest_override": latest_override,
        }

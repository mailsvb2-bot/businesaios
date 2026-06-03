from __future__ import annotations

from collections.abc import Sequence

from ..errors import DuplicateOverrideError
from ..types import OverrideRecord


class InMemoryOverrideRepository:
    def __init__(self) -> None:
        self._items_by_id: dict[str, OverrideRecord] = {}
        self._review_index: dict[str, list[str]] = {}

    def add(self, record: OverrideRecord) -> OverrideRecord:
        if record.override_id in self._items_by_id:
            raise DuplicateOverrideError(
                f"override '{record.override_id}' already exists"
            )

        self._items_by_id[record.override_id] = record
        self._review_index.setdefault(record.review_id, []).append(record.override_id)
        return record

    def get(self, override_id: str) -> OverrideRecord | None:
        return self._items_by_id.get(override_id)

    def list_for_review(self, review_id: str) -> Sequence[OverrideRecord]:
        ids = self._review_index.get(review_id, [])
        items = [self._items_by_id[item_id] for item_id in ids]
        items.sort(key=lambda item: (item.created_at, item.override_id))
        return items

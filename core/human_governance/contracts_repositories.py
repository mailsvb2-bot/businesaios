from __future__ import annotations

from typing import Protocol
from collections.abc import Sequence

from .types import OverrideRecord, ReviewItem


class ReviewRepository(Protocol):
    def get(self, review_id: str) -> ReviewItem | None: ...

    def upsert(self, item: ReviewItem) -> ReviewItem: ...

    def list_open(self, limit: int = 100) -> Sequence[ReviewItem]: ...


class OverrideRepository(Protocol):
    def add(self, record: OverrideRecord) -> OverrideRecord: ...

    def get(self, override_id: str) -> OverrideRecord | None: ...

    def list_for_review(self, review_id: str) -> Sequence[OverrideRecord]: ...

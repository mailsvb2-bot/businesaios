from __future__ import annotations

from typing import Protocol, Sequence

from .types import ApprovalState, EscalationRecord, ReviewItem


class ReviewQueueReader(Protocol):
    def read_queue(self, limit: int = 100) -> Sequence[ReviewItem]: ...


class ApprovalStateReader(Protocol):
    def read_state(self, review_id: str) -> ApprovalState | None: ...


class EscalationReader(Protocol):
    def read_open_escalations(self, limit: int = 100) -> Sequence[EscalationRecord]: ...

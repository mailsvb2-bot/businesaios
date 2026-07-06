from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class OutboxPort(Protocol):
    def enqueue(self, item: dict) -> None: ...
    def peek(self, limit: int = 50) -> Iterable[dict]: ...
    def mark_delivered(self, outbox_id: str) -> None: ...

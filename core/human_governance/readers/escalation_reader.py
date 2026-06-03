from __future__ import annotations

from collections.abc import Sequence

from ..types import EscalationRecord


class EscalationReaderImpl:
    def __init__(self, items: Sequence[EscalationRecord] | None = None) -> None:
        self._items = list(items or [])

    def read_open_escalations(self, limit: int = 100) -> Sequence[EscalationRecord]:
        open_items = [item for item in self._items if item.is_open]
        open_items.sort(key=lambda item: item.created_at)
        return open_items[:limit]

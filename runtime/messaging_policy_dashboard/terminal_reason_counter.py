from __future__ import annotations

from runtime.messaging_policy_dashboard.counter_ops import increment, sorted_counter_items


class TerminalReasonCounter:
    def __init__(self) -> None:
        self._items: dict[str, int] = {}

    def add(self, reason: str) -> None:
        increment(self._items, reason)

    def as_list(self) -> list[dict]:
        return [{'reason': key, 'count': value} for key, value in sorted_counter_items(self._items)]

from __future__ import annotations

from runtime.messaging_policy_dashboard.counter_ops import increment, sorted_counter_items


class ChannelCounters:
    def __init__(self) -> None:
        self.selected: dict[str, int] = {}
        self.delivered: dict[str, int] = {}
        self.failed: dict[str, int] = {}
        self.blocked: dict[str, int] = {}

    def add_selected(self, channel: str) -> None:
        increment(self.selected, channel)

    def add_delivered_many(self, items) -> None:
        for item in tuple(items or ()):
            increment(self.delivered, str(item))

    def add_failed_many(self, items) -> None:
        for item in tuple(items or ()):
            increment(self.failed, str(item))

    def add_blocked_many(self, items) -> None:
        for item in tuple(items or ()):
            increment(self.blocked, str(item))

    def as_dict(self) -> dict:
        return {
            'selected': [{'channel': key, 'count': value} for key, value in sorted_counter_items(self.selected)],
            'delivered': [{'channel': key, 'count': value} for key, value in sorted_counter_items(self.delivered)],
            'failed': [{'channel': key, 'count': value} for key, value in sorted_counter_items(self.failed)],
            'blocked': [{'channel': key, 'count': value} for key, value in sorted_counter_items(self.blocked)],
        }

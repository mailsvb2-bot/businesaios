from __future__ import annotations

from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging_capability.channel_health import ChannelHealth


class ChannelHealthRegistry:
    def __init__(self, *, items: tuple[ChannelHealth, ...] = ()) -> None:
        self._items: dict[str, ChannelHealth] = {item.channel: item for item in items}

    def set(self, health: ChannelHealth) -> None:
        self._items[health.channel] = health

    def get(self, channel: str) -> ChannelHealth:
        normalized = normalize_channel(channel)
        return self._items.get(normalized, ChannelHealth(channel=normalized))

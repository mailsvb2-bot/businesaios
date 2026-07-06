from __future__ import annotations

from contextlib import suppress

from runtime.messaging_capability.channel_health_registry import ChannelHealthRegistry


def resolve_channel_health_registry(runtime_obj) -> ChannelHealthRegistry:
    registry = getattr(runtime_obj, "messaging_channel_health_registry", None)
    if registry is None:
        registry = ChannelHealthRegistry()
        with suppress(Exception):
            runtime_obj.messaging_channel_health_registry = registry
    return registry

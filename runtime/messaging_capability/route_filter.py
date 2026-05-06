from __future__ import annotations

from runtime.messaging_capability.channel_capability_check import channel_supports_requirement


def filter_channels_by_capability(*, ordered_channels: tuple[str, ...], requirement) -> tuple[str, ...]:
    return tuple(
        channel for channel in tuple(ordered_channels or ())
        if channel_supports_requirement(channel=channel, requirement=requirement)
    )

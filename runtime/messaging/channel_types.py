"""Runtime compatibility surface for the canonical messaging channel catalog."""

from __future__ import annotations

from contracts.messaging_channels import (
    ALL_CHANNELS,
    CHANNEL_API,
    CHANNEL_DISCORD,
    CHANNEL_EMAIL,
    CHANNEL_INSTAGRAM,
    CHANNEL_KAKAOTALK,
    CHANNEL_LINE,
    CHANNEL_MAX,
    CHANNEL_MESSENGER,
    CHANNEL_SLACK,
    CHANNEL_SMS,
    CHANNEL_TELEGRAM,
    CHANNEL_VIBER,
    CHANNEL_VK,
    CHANNEL_WEB_CHAT,
    CHANNEL_WECHAT,
    CHANNEL_WHATSAPP,
)

# Mutable-list compatibility for historical callers. Channel identity remains
# owned exclusively by contracts.messaging_channels.ALL_CHANNELS.
CHANNELS = list(ALL_CHANNELS)

__all__ = [
    "ALL_CHANNELS",
    "CHANNELS",
    "CHANNEL_API",
    "CHANNEL_DISCORD",
    "CHANNEL_EMAIL",
    "CHANNEL_INSTAGRAM",
    "CHANNEL_KAKAOTALK",
    "CHANNEL_LINE",
    "CHANNEL_MAX",
    "CHANNEL_MESSENGER",
    "CHANNEL_SLACK",
    "CHANNEL_SMS",
    "CHANNEL_TELEGRAM",
    "CHANNEL_VIBER",
    "CHANNEL_VK",
    "CHANNEL_WEB_CHAT",
    "CHANNEL_WECHAT",
    "CHANNEL_WHATSAPP",
]

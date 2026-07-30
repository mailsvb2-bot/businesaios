"""Canonical identity catalog for every user-facing messaging channel.

This neutral contract is the sole owner of channel names. Runtime delivery,
ingress, growth strategy, configuration, capability and UI surfaces must consume
this catalog rather than maintaining parallel channel lists.
"""

from __future__ import annotations

CANON_MESSAGING_CHANNEL_CATALOG = True

CHANNEL_TELEGRAM = "telegram"
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_VK = "vk"
CHANNEL_MAX = "max"
CHANNEL_SMS = "sms"
CHANNEL_EMAIL = "email"
CHANNEL_MESSENGER = "messenger"
CHANNEL_INSTAGRAM = "instagram"
CHANNEL_WEB_CHAT = "web_chat"
CHANNEL_API = "api"
CHANNEL_LINE = "line"
CHANNEL_WECHAT = "wechat"
CHANNEL_KAKAOTALK = "kakaotalk"
CHANNEL_VIBER = "viber"
CHANNEL_SLACK = "slack"
CHANNEL_DISCORD = "discord"

ALL_CHANNELS = (
    CHANNEL_TELEGRAM,
    CHANNEL_WHATSAPP,
    CHANNEL_VK,
    CHANNEL_MAX,
    CHANNEL_SMS,
    CHANNEL_EMAIL,
    CHANNEL_MESSENGER,
    CHANNEL_INSTAGRAM,
    CHANNEL_WEB_CHAT,
    CHANNEL_API,
    CHANNEL_LINE,
    CHANNEL_WECHAT,
    CHANNEL_KAKAOTALK,
    CHANNEL_VIBER,
    CHANNEL_SLACK,
    CHANNEL_DISCORD,
)

__all__ = [
    "ALL_CHANNELS",
    "CANON_MESSAGING_CHANNEL_CATALOG",
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

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from interfaces.messaging_runtime.channel_aliases import canonical_channel_name


@dataclass(frozen=True)
class ChannelCapabilities:
    channel: str
    plain_text: bool
    html: bool
    buttons: bool
    attachments: bool
    structured_payload: bool
    subject_line: bool


DEFAULT_CAPABILITIES: Mapping[str, ChannelCapabilities] = {
    "telegram": ChannelCapabilities("telegram", True, False, True, True, False, False),
    "whatsapp": ChannelCapabilities("whatsapp", True, False, True, True, False, False),
    "vk": ChannelCapabilities("vk", True, False, True, True, False, False),
    "max": ChannelCapabilities("max", True, False, True, True, False, False),
    "sms": ChannelCapabilities("sms", True, False, False, False, False, False),
    "email": ChannelCapabilities("email", True, True, False, True, False, True),
    "messenger": ChannelCapabilities("messenger", True, False, True, True, False, False),
    "instagram": ChannelCapabilities("instagram", True, False, True, True, False, False),
    "viber": ChannelCapabilities("viber", True, False, True, True, False, False),
    "line": ChannelCapabilities("line", True, False, True, True, False, False),
    "wechat": ChannelCapabilities("wechat", True, False, True, True, False, False),
    "kakaotalk": ChannelCapabilities("kakaotalk", True, False, True, True, False, False),
    "slack": ChannelCapabilities("slack", True, False, True, True, True, False),
    "discord": ChannelCapabilities("discord", True, False, True, True, True, False),
    "web_chat": ChannelCapabilities("web_chat", True, False, True, False, False, False),
    "api": ChannelCapabilities("api", True, False, False, False, True, False),
}


def get_capabilities(channel: str) -> ChannelCapabilities:
    canonical = canonical_channel_name(channel)
    try:
        return DEFAULT_CAPABILITIES[canonical]
    except KeyError as exc:
        raise RuntimeError(f"capabilities not configured for channel: {channel}") from exc


__all__ = ["ChannelCapabilities", "DEFAULT_CAPABILITIES", "get_capabilities"]

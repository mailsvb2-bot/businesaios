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
    "sms": ChannelCapabilities("sms", True, False, False, False, False, False),
    "whatsapp": ChannelCapabilities("whatsapp", True, False, True, True, False, False),
    "email": ChannelCapabilities("email", True, True, False, True, False, True),
    "messenger": ChannelCapabilities("messenger", True, False, True, True, False, False),
    "viber": ChannelCapabilities("viber", True, False, True, True, False, False),
    "line": ChannelCapabilities("line", True, False, True, True, False, False),
    "wechat": ChannelCapabilities("wechat", True, False, True, True, False, False),
    "kakaotalk": ChannelCapabilities("kakaotalk", True, False, True, True, False, False),
    "webchat": ChannelCapabilities("webchat", True, False, True, False, False, False),
    "api_gateway": ChannelCapabilities("api_gateway", True, False, False, False, True, False),
}


def get_capabilities(channel: str) -> ChannelCapabilities:
    canonical = canonical_channel_name(channel)
    try:
        return DEFAULT_CAPABILITIES[canonical]
    except KeyError as exc:
        raise RuntimeError(f"capabilities not configured for channel: {channel}") from exc

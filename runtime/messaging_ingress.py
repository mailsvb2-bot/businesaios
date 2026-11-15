from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.ai.world_state import WorldStateV1
from runtime.messaging.channel_normalizer import normalize_channel, split_command
from runtime.messaging.channel_types import ALL_CHANNELS
from runtime.messaging.provider_inbound_decoder import decode_provider_inbound

CANON_MESSAGING_INGRESS_NORMALIZATION_ONLY = True
CANON_MESSAGING_SINGLE_WORLD_STATE_ADAPTER = True
CANON_MESSAGING_CONCRETE_ADAPTERS_TO_INGRESS_EVENT = True

# Retained only as a compatibility constant. VK and MAX are now complete
# channels and no longer need an ingress-only exception.
INGRESS_ONLY_MESSAGING_CHANNELS: tuple[str, ...] = ()
SUPPORTED_MESSAGING_CHANNELS = tuple(ALL_CHANNELS)


@dataclass(frozen=True)
class MessagingIngressEvent:
    channel: str
    user_id: str
    chat_id: str = ""
    text: str = ""
    command: str = ""
    args: str = ""
    tenant_id: str = "default"
    timestamp_ms: int = 0
    update_id: Any = None
    raw: dict[str, Any] = field(default_factory=dict)
    product_name: str = "BusinesAIOS"
    timezone: str = "Europe/Amsterdam"


def normalize_messaging_channel(channel: str) -> str:
    value = (
        str(channel or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )
    if not value:
        return "unknown"
    try:
        return normalize_channel(value)
    except ValueError:
        return value


def messaging_event_to_world_state(
    event: MessagingIngressEvent,
) -> WorldStateV1:
    channel = normalize_messaging_channel(event.channel)
    user_id = str(event.user_id or event.chat_id or "messaging_user")
    chat_id = str(event.chat_id or "")
    command = str(event.command or "")
    args = str(event.args or "")
    if not command:
        command, args = split_command(event.text)
    return WorldStateV1(
        schema_version=1,
        user={
            "id": user_id,
            "messaging_user_id": user_id,
            "messaging_chat_id": chat_id,
            "messaging_channel": channel,
            "timezone": str(event.timezone or "Europe/Amsterdam"),
        },
        session={
            "source": "messaging",
            "channel": channel,
            "text": str(event.text or ""),
            "command": command,
            "args": args,
            "messaging_update_id": event.update_id,
            "messaging_chat_id": chat_id,
        },
        product={
            "name": str(event.product_name or "BusinesAIOS"),
            "channel": channel,
        },
        economy={},
        timestamp_ms=int(event.timestamp_ms or 0),
        tenant_id=str(event.tenant_id or "default"),
        user_id=user_id,
        meta={
            "source": "messaging",
            "channel": channel,
            "supported_channel": channel in SUPPORTED_MESSAGING_CHANNELS,
        },
    )


def payload_to_messaging_event(
    channel: str,
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    normalized_channel = normalize_messaging_channel(channel)
    decoded = decode_provider_inbound(
        channel=normalized_channel,
        payload=payload,
    )
    text = str(decoded.get("text") or "")
    command, args = split_command(text)
    user_id = str(decoded.get("user_id") or decoded.get("chat_id") or "")
    if not user_id:
        user_id = f"{normalized_channel}_user"
    return MessagingIngressEvent(
        channel=normalized_channel,
        user_id=user_id,
        chat_id=str(decoded.get("chat_id") or ""),
        text=text,
        command=command,
        args=args,
        tenant_id=tenant_id,
        timestamp_ms=int(decoded.get("timestamp_ms") or 0),
        update_id=decoded.get("message_id"),
        raw=dict(payload or {}),
        product_name=product_name,
        timezone=timezone,
    )


def telegram_update_to_messaging_event(
    update: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    event = payload_to_messaging_event(
        "telegram",
        update,
        tenant_id=tenant_id,
        product_name=product_name,
        timezone=timezone,
    )
    update_id = dict(update or {}).get("update_id")
    if update_id is None:
        return event
    return MessagingIngressEvent(
        channel=event.channel,
        user_id=event.user_id,
        chat_id=event.chat_id,
        text=event.text,
        command=event.command,
        args=event.args,
        tenant_id=event.tenant_id,
        timestamp_ms=event.timestamp_ms,
        update_id=update_id,
        raw=event.raw,
        product_name=event.product_name,
        timezone=event.timezone,
    )


def _provider_event(
    channel: str,
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str,
    timezone: str,
) -> MessagingIngressEvent:
    return payload_to_messaging_event(
        channel,
        payload,
        tenant_id=tenant_id,
        product_name=product_name,
        timezone=timezone,
    )


def _provider_adapter(channel: str):
    """Compatibility names sharing the one canonical provider normalization path."""
    def adapter(payload: dict[str, Any], *, tenant_id: str,
                product_name: str = "BusinesAIOS", timezone: str = "Europe/Amsterdam") -> MessagingIngressEvent:
        return _provider_event(channel, payload, tenant_id=tenant_id,
                               product_name=product_name, timezone=timezone)
    adapter.__name__ = f"{channel.replace('_', '')}_payload_to_messaging_event"
    adapter.__qualname__ = adapter.__name__
    return adapter


whatsapp_payload_to_messaging_event = _provider_adapter("whatsapp")
vk_payload_to_messaging_event = _provider_adapter("vk")
max_payload_to_messaging_event = _provider_adapter("max")
slack_payload_to_messaging_event = _provider_adapter("slack")
discord_payload_to_messaging_event = _provider_adapter("discord")
viber_payload_to_messaging_event = _provider_adapter("viber")
sms_payload_to_messaging_event = _provider_adapter("sms")
email_payload_to_messaging_event = _provider_adapter("email")
webchat_payload_to_messaging_event = _provider_adapter("web_chat")
instagram_payload_to_messaging_event = _provider_adapter("instagram")
messenger_payload_to_messaging_event = _provider_adapter("messenger")
line_payload_to_messaging_event = _provider_adapter("line")
wechat_payload_to_messaging_event = _provider_adapter("wechat")
kakaotalk_payload_to_messaging_event = _provider_adapter("kakaotalk")
api_payload_to_messaging_event = _provider_adapter("api")


__all__ = [
    "CANON_MESSAGING_CONCRETE_ADAPTERS_TO_INGRESS_EVENT",
    "CANON_MESSAGING_INGRESS_NORMALIZATION_ONLY",
    "CANON_MESSAGING_SINGLE_WORLD_STATE_ADAPTER",
    "INGRESS_ONLY_MESSAGING_CHANNELS",
    "MessagingIngressEvent",
    "SUPPORTED_MESSAGING_CHANNELS",
    "api_payload_to_messaging_event",
    "discord_payload_to_messaging_event",
    "email_payload_to_messaging_event",
    "instagram_payload_to_messaging_event",
    "kakaotalk_payload_to_messaging_event",
    "line_payload_to_messaging_event",
    "max_payload_to_messaging_event",
    "messaging_event_to_world_state",
    "messenger_payload_to_messaging_event",
    "normalize_messaging_channel",
    "payload_to_messaging_event",
    "slack_payload_to_messaging_event",
    "sms_payload_to_messaging_event",
    "split_command",
    "telegram_update_to_messaging_event",
    "viber_payload_to_messaging_event",
    "vk_payload_to_messaging_event",
    "webchat_payload_to_messaging_event",
    "wechat_payload_to_messaging_event",
    "whatsapp_payload_to_messaging_event",
]

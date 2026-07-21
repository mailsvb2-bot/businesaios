from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.ai.world_state import WorldStateV1
from runtime.messaging.channel_normalizer import normalize_channel
from runtime.messaging.channel_types import ALL_CHANNELS

CANON_MESSAGING_INGRESS_NORMALIZATION_ONLY = True
CANON_MESSAGING_SINGLE_WORLD_STATE_ADAPTER = True
CANON_MESSAGING_CONCRETE_ADAPTERS_TO_INGRESS_EVENT = True

INGRESS_ONLY_MESSAGING_CHANNELS = ("vk", "max")
SUPPORTED_MESSAGING_CHANNELS = tuple(dict.fromkeys((*ALL_CHANNELS, *INGRESS_ONLY_MESSAGING_CHANNELS)))

_INGRESS_COMPAT_ALIASES = {
    "telegram_bot": "telegram",
    "whats_app": "whatsapp",
    "vkontakte": "vk",
    "vk_bot": "vk",
    "mail": "email",
    "e_mail": "email",
}


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
    value = str(channel or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not value:
        return "unknown"
    candidate = _INGRESS_COMPAT_ALIASES.get(value, value)
    try:
        return normalize_channel(candidate)
    except ValueError:
        return candidate


def split_command(text: str) -> tuple[str, str]:
    stripped = str(text or "").strip()
    if not stripped.startswith("/"):
        return "", stripped
    head, _, tail = stripped.partition(" ")
    return head, tail.strip()


def messaging_event_to_world_state(event: MessagingIngressEvent) -> WorldStateV1:
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
    normalized = normalize_messaging_channel(channel)
    body = dict(payload or {})
    text = _first_text(body, "text", "message", "body", "caption", "content", "subject")
    command, args = split_command(text)
    return MessagingIngressEvent(
        channel=normalized,
        user_id=(
            _first_text(body, "user_id", "from_id", "sender_id", "author_id", "phone", "email")
            or f"{normalized}_user"
        ),
        chat_id=(
            _first_text(body, "chat_id", "peer_id", "conversation_id", "channel_id", "thread_id", "to")
            or ""
        ),
        text=text,
        command=command,
        args=args,
        tenant_id=tenant_id,
        timestamp_ms=_first_int(body, "timestamp_ms", "date_ms", "created_at_ms", "ts_ms"),
        update_id=_first_value(body, "update_id", "event_id", "message_id", "id"),
        raw=body,
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
    body = dict(update or {})
    message = _telegram_message(body)
    text = _telegram_text(body, message)
    command, args = split_command(text)
    chat_id = _telegram_chat_id(message)
    user_id = _telegram_sender_id(body, message) or chat_id or "telegram_user"
    message_date = _first_int(message, "date")
    timestamp_ms = message_date * 1000 if message_date > 0 else 0
    return MessagingIngressEvent(
        channel="telegram",
        user_id=user_id,
        chat_id=chat_id,
        text=text,
        command=command,
        args=args,
        tenant_id=tenant_id,
        timestamp_ms=timestamp_ms,
        update_id=body.get("update_id"),
        raw=body,
        product_name=product_name,
        timezone=timezone,
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


def whatsapp_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event(
        "whatsapp",
        payload,
        tenant_id=tenant_id,
        product_name=product_name,
        timezone=timezone,
    )


def vk_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("vk", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def max_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("max", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def slack_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("slack", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def discord_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("discord", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def viber_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("viber", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def sms_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("sms", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def email_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("email", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def webchat_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("web_chat", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def instagram_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("instagram", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def messenger_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("messenger", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def line_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("line", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def wechat_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("wechat", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def kakaotalk_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("kakaotalk", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def api_payload_to_messaging_event(
    payload: dict[str, Any],
    *,
    tenant_id: str,
    product_name: str = "BusinesAIOS",
    timezone: str = "Europe/Amsterdam",
) -> MessagingIngressEvent:
    return _provider_event("api", payload, tenant_id=tenant_id, product_name=product_name, timezone=timezone)


def _first_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _first_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload.get(key) is not None:
            return payload.get(key)
    return None


def _first_int(payload: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _telegram_message(update: dict[str, Any]) -> dict[str, Any]:
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        value = update.get(key)
        if isinstance(value, dict):
            return value
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        value = callback.get("message")
        if isinstance(value, dict):
            return value
    return {}


def _telegram_text(update: dict[str, Any], message: dict[str, Any]) -> str:
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        data = str(callback.get("data") or "").strip()
        if data:
            return data
    return str(message.get("text") or message.get("caption") or "").strip()


def _telegram_chat_id(message: dict[str, Any]) -> str:
    chat = message.get("chat")
    if isinstance(chat, dict) and chat.get("id") is not None:
        return str(chat.get("id"))
    return ""


def _telegram_sender_id(update: dict[str, Any], message: dict[str, Any]) -> str:
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        sender = callback.get("from")
        if isinstance(sender, dict) and sender.get("id") is not None:
            return str(sender.get("id"))
    sender = message.get("from")
    if isinstance(sender, dict) and sender.get("id") is not None:
        return str(sender.get("id"))
    return ""


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

"""Canonical provider webhook/update decoder for every messaging channel.

Provider payloads are nested and differ by transport. This module is the sole
owner of extracting the stable messaging envelope fields used by bindings and
WorldState ingress. Channel packages may delegate here but must not maintain
parallel path tables.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from contracts.messaging_event_identity import stable_transport_message_id
from runtime.messaging.channel_normalizer import normalize_channel

PathPart = str | int
FieldPath = tuple[PathPart, ...]

_PROVIDER_PATHS: dict[str, dict[str, tuple[FieldPath, ...]]] = {
    "telegram": {
        "user_id": (
            ("message", "from", "id"),
            ("callback_query", "from", "id"),
            ("edited_message", "from", "id"),
        ),
        "chat_id": (
            ("message", "chat", "id"),
            ("callback_query", "message", "chat", "id"),
            ("edited_message", "chat", "id"),
        ),
        "text": (
            ("message", "text"),
            ("message", "caption"),
            ("callback_query", "data"),
            ("callback_query", "message", "text"),
            ("callback_query", "message", "caption"),
            ("edited_message", "text"),
            ("edited_message", "caption"),
        ),
        "message_id": (
            ("message", "message_id"),
            ("callback_query", "id"),
            ("update_id",),
        ),
        "timestamp": (
            ("message", "date"),
            ("callback_query", "message", "date"),
            ("edited_message", "date"),
        ),
        "name": (
            ("message", "from", "username"),
            ("message", "from", "first_name"),
            ("callback_query", "from", "username"),
        ),
    },
    "whatsapp": {
        "user_id": (
            ("entry", 0, "changes", 0, "value", "messages", 0, "from"),
            ("entry", 0, "changes", 0, "value", "contacts", 0, "wa_id"),
        ),
        "chat_id": (
            ("entry", 0, "changes", 0, "value", "messages", 0, "from"),
        ),
        "text": (
            ("entry", 0, "changes", 0, "value", "messages", 0, "text", "body"),
            ("entry", 0, "changes", 0, "value", "messages", 0, "button", "text"),
            ("entry", 0, "changes", 0, "value", "messages", 0, "interactive", "button_reply", "title"),
            ("entry", 0, "changes", 0, "value", "messages", 0, "interactive", "list_reply", "title"),
        ),
        "message_id": (
            ("entry", 0, "changes", 0, "value", "messages", 0, "id"),
        ),
        "timestamp": (
            ("entry", 0, "changes", 0, "value", "messages", 0, "timestamp"),
        ),
        "name": (
            ("entry", 0, "changes", 0, "value", "contacts", 0, "profile", "name"),
        ),
    },
    "messenger": {
        "user_id": (("entry", 0, "messaging", 0, "sender", "id"),),
        "chat_id": (("entry", 0, "messaging", 0, "sender", "id"),),
        "text": (
            ("entry", 0, "messaging", 0, "message", "text"),
            ("entry", 0, "messaging", 0, "postback", "title"),
            ("entry", 0, "messaging", 0, "postback", "payload"),
            ("message",),
        ),
        "message_id": (("entry", 0, "messaging", 0, "message", "mid"),),
        "timestamp": (("entry", 0, "messaging", 0, "timestamp"),),
    },
    "instagram": {
        "user_id": (("entry", 0, "messaging", 0, "sender", "id"),),
        "chat_id": (("entry", 0, "messaging", 0, "sender", "id"),),
        "text": (
            ("entry", 0, "messaging", 0, "message", "text"),
            ("entry", 0, "messaging", 0, "postback", "title"),
        ),
        "message_id": (("entry", 0, "messaging", 0, "message", "mid"),),
        "timestamp": (("entry", 0, "messaging", 0, "timestamp"),),
    },
    "vk": {
        "user_id": (
            ("object", "message", "from_id"),
            ("object", "message", "user_id"),
            ("object", "user_id"),
            ("object", "from_id"),
        ),
        "chat_id": (
            ("object", "message", "peer_id"),
            ("object", "message", "conversation_message_id"),
            ("object", "peer_id"),
        ),
        "text": (
            ("object", "payload", "callback_data"),
            ("object", "payload", "command"),
            ("object", "message", "payload", "callback_data"),
            ("object", "message", "payload", "command"),
            ("object", "message", "text"),
        ),
        "message_id": (
            ("event_id",),
            ("object", "event_id"),
            ("object", "message", "id"),
            ("object", "message", "conversation_message_id"),
        ),
        "timestamp": (("object", "message", "date"),),
    },
    "max": {
        "user_id": (
            ("message", "sender", "user_id"),
            ("callback", "user", "user_id"),
            ("user", "user_id"),
        ),
        "chat_id": (
            ("message", "recipient", "chat_id"),
            ("message", "recipient", "user_id"),
            ("chat_id",),
        ),
        "text": (
            ("message", "body", "text"),
            ("callback", "payload"),
            ("message", "body", "command"),
        ),
        "message_id": (
            ("message", "body", "mid"),
            ("message", "body", "message_id"),
            ("update_id",),
        ),
        "timestamp": (("timestamp",), ("message", "timestamp")),
        "name": (
            ("message", "sender", "name"),
            ("user", "name"),
        ),
    },
    "slack": {
        "user_id": (("event", "user"), ("user_id",)),
        "chat_id": (("event", "channel"), ("channel_id",)),
        "text": (("event", "text"), ("text",)),
        "message_id": (("event_id",), ("event", "client_msg_id"), ("event", "ts")),
        "timestamp": (("event_time",), ("event", "event_ts"), ("event", "ts")),
    },
    "discord": {
        "user_id": (("author", "id"), ("member", "user", "id"), ("user", "id")),
        "chat_id": (("channel_id",), ("guild_id",)),
        "text": (("content",), ("data", "name"), ("message", "content")),
        "message_id": (("id",), ("message", "id")),
        "timestamp": (("timestamp",),),
        "name": (("author", "username"), ("member", "user", "username")),
    },
    "viber": {
        "user_id": (("sender", "id"), ("user", "id")),
        "chat_id": (("chat_id",), ("sender", "id")),
        "text": (("message", "text"), ("message", "tracking_data")),
        "message_id": (("message_token",), ("message", "id")),
        "timestamp": (("timestamp",),),
        "name": (("sender", "name"),),
    },
    "line": {
        "user_id": (("events", 0, "source", "userId"),),
        "chat_id": (
            ("events", 0, "source", "groupId"),
            ("events", 0, "source", "roomId"),
            ("events", 0, "source", "userId"),
        ),
        "text": (("events", 0, "message", "text"), ("events", 0, "postback", "data")),
        "message_id": (("events", 0, "message", "id"), ("events", 0, "webhookEventId")),
        "timestamp": (("events", 0, "timestamp"),),
    },
    "wechat": {
        "user_id": (("FromUserName",), ("from_user_name",)),
        "chat_id": (("ToUserName",), ("to_user_name",)),
        "text": (("Content",), ("content",)),
        "message_id": (("MsgId",), ("msg_id",)),
        "timestamp": (("CreateTime",), ("create_time",)),
    },
    "kakaotalk": {
        "user_id": (("userRequest", "user", "id"),),
        "chat_id": (("userRequest", "user", "properties", "plusfriendUserKey"),),
        "text": (("userRequest", "utterance"),),
        "message_id": (("userRequest", "block", "id"),),
        "timestamp": (("userRequest", "timestamp"),),
    },
    "sms": {
        "user_id": (("from",), ("phone",), ("sender_id",)),
        "chat_id": (("to",), ("recipient",)),
        "text": (("body",), ("text",), ("message",)),
        "message_id": (("message_id",), ("sid",), ("id",)),
        "timestamp": (("timestamp",), ("date",)),
    },
    "email": {
        "user_id": (("from",), ("email",), ("sender",)),
        "chat_id": (("to",), ("recipient",)),
        "text": (("text",), ("body",), ("html",)),
        "message_id": (("message_id",), ("Message-ID",), ("id",)),
        "timestamp": (("timestamp",), ("date",)),
        "subject": (("subject",),),
        "name": (("from_name",), ("name",)),
    },
}

_GENERIC_KEYS = {
    "user_id": ("user_id", "from_id", "sender_id", "author_id", "phone", "email", "wa_id"),
    "chat_id": ("chat_id", "peer_id", "conversation_id", "channel_id", "thread_id", "to"),
    "text": ("text", "body", "caption", "content", "subject", "utterance"),
    "message_id": ("update_id", "event_id", "message_id", "client_msg_id", "mid"),
    "timestamp": ("timestamp_ms", "timestamp", "date_ms", "created_at_ms", "event_time", "date", "ts"),
    "locale": ("locale", "language", "lang"),
    "subject": ("subject",),
    "name": ("name", "username", "display_name", "first_name"),
}


def _path_value(payload: Any, path: FieldPath) -> Any:
    current = payload
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, Sequence) or isinstance(current, str | bytes):
                return None
            if part < 0 or part >= len(current):
                return None
            current = current[part]
            continue
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _scalar_value(value: Any) -> Any:
    if value is None or isinstance(value, Mapping | list | tuple | set):
        return None
    return value


def _scalar_text(value: Any) -> str:
    scalar = _scalar_value(value)
    return "" if scalar is None else str(scalar).strip()


def _first_path_value(payload: Mapping[str, Any], paths: tuple[FieldPath, ...]) -> Any:
    for path in paths:
        value = _scalar_value(_path_value(payload, path))
        if value is not None and str(value).strip():
            return value
    return None


def _nested_mappings(payload: Mapping[str, Any], *, limit: int = 256):
    queue = deque([payload])
    seen = 0
    while queue and seen < limit:
        current = queue.popleft()
        seen += 1
        if isinstance(current, Mapping):
            yield current
            for value in current.values():
                if isinstance(value, Mapping):
                    queue.append(value)
                elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
                    queue.extend(item for item in value if isinstance(item, Mapping))


def _deep_first_value(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for node in _nested_mappings(payload):
        for key in keys:
            if key not in node:
                continue
            value = _scalar_value(node.get(key))
            if value is not None and str(value).strip():
                return value
    return None


def _timestamp_ms(value: Any, *, already_ms: bool = False) -> int:
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        numeric = float(raw)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return 0
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return int(parsed.timestamp() * 1000)
    if numeric < 0:
        return 0
    if already_ms:
        return int(numeric)
    return int(numeric if numeric >= 1_000_000_000_000 else numeric * 1000)


def _timestamp_from_payload(
    payload: Mapping[str, Any],
    explicit_paths: tuple[FieldPath, ...],
) -> int:
    for path in explicit_paths:
        value = _scalar_value(_path_value(payload, path))
        if value is None:
            continue
        parsed = _timestamp_ms(value, already_ms=str(path[-1]).endswith("_ms"))
        if parsed:
            return parsed
    for node in _nested_mappings(payload):
        for key in _GENERIC_KEYS["timestamp"]:
            if key not in node:
                continue
            parsed = _timestamp_ms(node.get(key), already_ms=key.endswith("_ms"))
            if parsed:
                return parsed
    return 0


def _canonical_or_passthrough(channel: str) -> str:
    raw = str(channel or "").strip().lower().replace("-", "_").replace(" ", "_")
    try:
        return normalize_channel(raw)
    except ValueError:
        return raw or "unknown"


def decode_provider_inbound(
    *,
    channel: str,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    canonical = _canonical_or_passthrough(channel)
    raw = dict(payload or {})
    paths = _PROVIDER_PATHS.get(canonical, {})

    def field_value(name: str) -> Any:
        explicit = _first_path_value(raw, paths.get(name, ()))
        if explicit is not None:
            return explicit
        return _deep_first_value(raw, _GENERIC_KEYS.get(name, ()))

    def field_text(name: str) -> str:
        return _scalar_text(field_value(name))

    user_id = field_text("user_id")
    chat_id = field_text("chat_id")
    if not user_id:
        user_id = chat_id

    provider_message_id = _first_path_value(raw, paths.get("message_id", ()))
    if provider_message_id is None:
        for key in ("update_id", "event_id", "message_id", "client_msg_id", "id", "mid"):
            value = _scalar_value(raw.get(key))
            if value is not None and str(value).strip():
                provider_message_id = value
                break
    if provider_message_id is None:
        provider_message_id = _deep_first_value(raw, _GENERIC_KEYS["message_id"])
    message_id = (
        provider_message_id
        if provider_message_id is not None and str(provider_message_id).strip()
        else stable_transport_message_id(channel=canonical, payload=raw)
    )
    return {
        "channel": canonical,
        "user_id": user_id,
        "chat_id": chat_id,
        "text": field_text("text"),
        "message_id": message_id,
        "external_user_ref": user_id or chat_id,
        "timestamp_ms": _timestamp_from_payload(raw, paths.get("timestamp", ())),
        "locale": field_text("locale") or None,
        "subject": field_text("subject") or None,
        "name": field_text("name") or None,
        "raw": raw,
    }


__all__ = ["decode_provider_inbound"]

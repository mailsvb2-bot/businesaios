from __future__ import annotations

from typing import Any
from collections.abc import Mapping


def pick(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping and mapping.get(name) not in (None, ""):
            return mapping.get(name)
    return None


def text_from_payload(payload: Mapping[str, Any]) -> str:
    return str(pick(payload, "text", "body", "message", "caption") or "")


def user_id_from_payload(payload: Mapping[str, Any]) -> str:
    return str(pick(payload, "user_id", "from_id", "sender_id", "chat_id", "session_id") or "")


def message_id_from_payload(payload: Mapping[str, Any]) -> str:
    return str(pick(payload, "message_id", "update_id", "event_id", "client_message_id") or "")


def correlation_id_from_payload(payload: Mapping[str, Any], *, fallback_message_id: str) -> str:
    return str(pick(payload, "correlation_id", "request_id", "trace_id") or fallback_message_id or "")


def external_user_ref_from_payload(payload: Mapping[str, Any], *, fallback_user_id: str) -> str:
    return str(
        pick(payload, "external_user_ref", "phone", "email", "wa_id", "session_id", "chat_id", "user_id")
        or fallback_user_id
    )


def metadata_from_payload(payload: Mapping[str, Any], *, channel: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "channel": str(channel),
        "payload_keys": tuple(sorted(str(k) for k in payload)),
    }
    for key in ("subject", "name", "locale", "channel_account_id", "web_session_id"):
        if key in payload:
            out[key] = payload.get(key)
    return out

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from interfaces.messaging._shared.runner_helpers import normalize_inbound_dict


def normalize_provider_inbound(*, provider_channel: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
    p = normalize_inbound_dict(dict(payload or {}))
    return {
        "channel": provider_channel,
        "user_id": str(
            p.get("user_id")
            or p.get("from_id")
            or p.get("sender_id")
            or p.get("chat_id")
            or p.get("session_id")
            or ""
        ),
        "text": str(p.get("text") or p.get("body") or p.get("message") or ""),
        "message_id": str(p.get("message_id") or p.get("event_id") or p.get("update_id") or ""),
        "external_user_ref": str(
            p.get("external_user_ref")
            or p.get("phone")
            or p.get("email")
            or p.get("wa_id")
            or p.get("chat_id")
            or p.get("session_id")
            or p.get("user_id")
            or ""
        ),
        "locale": p.get("locale"),
        "subject": p.get("subject"),
        "name": p.get("name"),
    }

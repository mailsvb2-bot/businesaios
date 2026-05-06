from __future__ import annotations

from typing import Any, Mapping


def normalize_widget_inbound(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    p = dict(payload or {})
    return {
        "channel": "web_chat",
        "user_id": str(p.get("user_id") or p.get("session_id") or ""),
        "text": str(p.get("text") or ""),
        "message_id": str(p.get("message_id") or p.get("client_message_id") or ""),
        "external_user_ref": str(p.get("session_id") or p.get("user_id") or ""),
        "web_session_id": str(p.get("session_id") or ""),
        "name": p.get("name"),
        "locale": p.get("locale"),
    }

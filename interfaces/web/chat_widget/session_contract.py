from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CANON_WEB_CHAT_SESSION_CONTRACT = True


@dataclass
class WebChatSession:
    session_id: str
    tenant_id: str
    user_id: str
    channel: str = "web_chat"
    metadata: dict[str, Any] = field(default_factory=dict)


def web_chat_session_schema() -> dict[str, object]:
    return {"type": "object", "required": ["session_id", "tenant_id", "user_id", "channel", "metadata"], "properties": {"session_id": {"type": "string", "minLength": 1}, "tenant_id": {"type": "string", "minLength": 1}, "user_id": {"type": "string", "minLength": 1}, "channel": {"type": "string", "const": "web_chat"}, "metadata": {"type": "object"}}, "additionalProperties": False}


__all__ = ["CANON_WEB_CHAT_SESSION_CONTRACT", "WebChatSession", "web_chat_session_schema"]

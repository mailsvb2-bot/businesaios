from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WebChatSession:
    session_id: str
    tenant_id: str
    user_id: str
    channel: str = "web_chat"
    metadata: dict[str, Any] = field(default_factory=dict)

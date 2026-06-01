from __future__ import annotations

from dataclasses import dataclass

RUNTIME_MESSAGING_ROUTER_CONTRACT_VERSION = "RMR-CONTRACT-V1"


@dataclass(frozen=True)
class ConversationRoute:
    channel: str
    user_id: str
    conversation_id: str

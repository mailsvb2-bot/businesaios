from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TelegramIncomingMessage:
    chat_id: str
    user_id: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TelegramOutgoingMessage:
    chat_id: str
    text: str

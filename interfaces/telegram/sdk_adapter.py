from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TelegramSDKAdapter:
    bot_token: str

    def send_text(self, *, chat_id: str, text: str) -> None:
        _ = (chat_id, text, self.bot_token)

    def poll_updates(self) -> list[dict]:
        return []

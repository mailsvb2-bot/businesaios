from __future__ import annotations

from dataclasses import dataclass

from interfaces.telegram.telegram_action_models import TelegramIncomingMessage


@dataclass(frozen=True)
class TelegramAction:
    action_type: str
    payload: dict


def map_telegram_message_to_action(message: TelegramIncomingMessage) -> TelegramAction:
    return TelegramAction(
        action_type="telegram_message",
        payload={
            "chat_id": message.chat_id,
            "user_id": message.user_id,
            "text": message.text,
            "metadata": dict(message.metadata),
        },
    )

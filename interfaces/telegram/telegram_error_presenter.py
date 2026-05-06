from __future__ import annotations

from interfaces.telegram.telegram_action_models import TelegramOutgoingMessage


def present_telegram_error(
    *,
    chat_id: str,
    exc: Exception,
) -> TelegramOutgoingMessage:
    return TelegramOutgoingMessage(
        chat_id=chat_id,
    )

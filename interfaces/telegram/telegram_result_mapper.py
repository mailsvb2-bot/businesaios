from __future__ import annotations

from application.decision.action_result import ActionExecutionResult
from interfaces.telegram.telegram_action_models import TelegramOutgoingMessage
from interfaces.telegram.telegram_presenter import present_telegram_success


def map_result_to_telegram_message(
    *,
    chat_id: str,
    result: ActionExecutionResult,
) -> TelegramOutgoingMessage:
    return present_telegram_success(
        chat_id=chat_id,
        result=result,
    )

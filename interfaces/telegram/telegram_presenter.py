from __future__ import annotations

from application.decision.action_result import ActionExecutionResult
from interfaces.telegram.telegram_action_models import TelegramOutgoingMessage


def present_telegram_success(
    *,
    chat_id: str,
    result: ActionExecutionResult,
) -> TelegramOutgoingMessage:
    if result.status == "blocked":
        text = "Action blocked by governance."
    else:
        text = "Action accepted."

    return TelegramOutgoingMessage(
        chat_id=chat_id,
        text=text,
    )

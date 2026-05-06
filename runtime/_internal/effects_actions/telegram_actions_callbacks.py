from __future__ import annotations

from typing import Any

from runtime._internal.effects_actions.telegram.callbacks import answer_callback_effect


def answer_callback_internal_effect(
    effects: Any,
    *,
    callback_query_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    answer_callback_effect(
        effects,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        user_id=str(user_id),
        callback_query_id=str(callback_query_id),
        text=text,
        show_alert=show_alert,
    )


def answer_callback_public_effect(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    user_id: str,
    callback_query_id: str,
    text: str | None = None,
    show_alert: bool = False,
) -> Any:
    return answer_callback_effect(
        effects,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        user_id=str(user_id),
        callback_query_id=str(callback_query_id),
        text=text,
        show_alert=show_alert,
    )

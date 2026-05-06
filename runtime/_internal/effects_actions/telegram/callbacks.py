from __future__ import annotations

from typing import Any

from runtime._internal.router_support import execute_effect_action_sync
from runtime._internal.effect_types import EffectActionType


def answer_callback_effect(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    user_id: str,
    callback_query_id: str,
    text: str | None = None,
    show_alert: bool = False,
) -> dict:
    """Best-effort Telegram answerCallbackQuery with observability."""
    from runtime.security.runtime_asserts import assert_called_from_executor

    assert_called_from_executor()
    cbid = str(callback_query_id or "").strip()
    if not cbid:
        return {"ok": True, "meta": {"mode": "noop"}}

    try:
        execute_effect_action_sync(
            effects,
            EffectActionType.TELEGRAM_ANSWER_CALLBACK,
            {
                "callback_query_id": cbid,
                "text": (str(text).strip() if isinstance(text, str) and text.strip() else None),
                "show_alert": bool(show_alert),
            },
        )
    except Exception:
        # UX best-effort: never raise
        effects.event_log.emit(
            event_type="telegram_callback_answer_failed",
            source="runtime_effects",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"callback_query_id": cbid, "show_alert": bool(show_alert)},
        )
        return {"ok": True, "meta": {"mode": "best_effort", "delivered": False}}

    effects.event_log.emit(
        event_type="telegram_callback_answered",
        source="runtime_effects",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={"callback_query_id": cbid, "show_alert": bool(show_alert)},
    )
    return {"ok": True, "meta": {"mode": "best_effort", "delivered": True}}

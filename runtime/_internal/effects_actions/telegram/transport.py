from __future__ import annotations

from typing import Any

from runtime._internal.effect_types import EffectActionType
from runtime._internal.router_support import execute_effect_action_sync


def telegram_send_chat_action(effects: Any, *, chat_id: str, action: str = "typing") -> None:
    try:
        execute_effect_action_sync(
            effects,
            EffectActionType.TELEGRAM_SEND_CHAT_ACTION,
            {"chat_id": str(chat_id), "action": str(action or "typing")},
        )
    except Exception:
        return


def telegram_send_message_transport(
    effects: Any,
    *,
    chat_id: str,
    text: str,
    reply_markup: dict[str, Any] | None = None,
    priority: Any = "normal",
    critical: bool = True,
) -> tuple[bool, dict[str, Any]]:
    out = execute_effect_action_sync(
        effects,
        EffectActionType.TELEGRAM_SEND_MESSAGE,
        {
            "chat_id": str(chat_id),
            "text": str(text),
            "reply_markup": reply_markup if isinstance(reply_markup, dict) else None,
            "priority": priority,
            "critical": bool(critical),
        },
    )
    return bool(out.get("ok", False)), dict(out)

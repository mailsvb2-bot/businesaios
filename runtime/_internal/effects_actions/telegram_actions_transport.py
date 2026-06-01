from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from runtime._internal.effects_actions.telegram.transport import (
    telegram_send_audio_transport,
    telegram_send_chat_action,
    telegram_send_message_transport,
)


def send_chat_action_effect(effects: Any, *, chat_id: str, action: str = "typing") -> None:
    telegram_send_chat_action(effects, chat_id=str(chat_id), action=str(action or "typing"))


def send_message_transport_effect(
    effects: Any,
    *,
    chat_id: str,
    text: str,
    reply_markup: dict[str, Any] | None = None,
    priority: Any = "normal",
    critical: bool = True,
) -> tuple[bool, dict[str, Any]]:
    return telegram_send_message_transport(
        effects,
        chat_id=str(chat_id),
        text=str(text),
        reply_markup=reply_markup,
        priority=priority,
        critical=bool(critical),
    )


def send_audio_transport_effect(
    effects: Any,
    *,
    chat_id: str,
    audio_url: str,
    caption: str | None = None,
    priority: Any = "normal",
    critical: bool = True,
) -> tuple[bool, dict[str, Any]]:
    return telegram_send_audio_transport(
        effects,
        chat_id=str(chat_id),
        audio_url=str(audio_url),
        caption=caption,
        priority=priority,
        critical=bool(critical),
    )

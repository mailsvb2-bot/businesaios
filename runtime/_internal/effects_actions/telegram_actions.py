from __future__ import annotations

"""Sealed effect actions mixin.

This module is INTERNAL to runtime/_internal.
No API changes to EffectsPort.
"""

from typing import Any
from runtime.observability.telemetry import CANON_RUNTIME_TELEMETRY_OWNER as _CANON_RUNTIME_TELEMETRY_OWNER
CANON_RUNTIME_OBSERVABILITY_OWNER = _CANON_RUNTIME_TELEMETRY_OWNER

from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_actions.telegram.media import send_audio_effect
from runtime._internal.effects_actions.telegram.messaging import send_message_effect
from runtime._internal.effects_actions.telegram_actions_callbacks import (
    answer_callback_internal_effect,
    answer_callback_public_effect,
)
from runtime._internal.effects_actions.telegram_actions_polling import poll_telegram_updates_effect
from runtime._internal.effects_actions.telegram_actions_transport import (
    send_audio_transport_effect,
    send_chat_action_effect,
    send_message_transport_effect,
)


def telegram_self_check_effect(effects: Any, *, token: str | None = None) -> dict:
    from runtime._internal.router_support import execute_effect_action_sync

    return execute_effect_action_sync(effects, EffectActionType.TELEGRAM_SELF_CHECK, {"token": token})


class TelegramEffectsMixin:
    def telegram_self_check(self, *, token: str | None = None) -> dict:
        return telegram_self_check_effect(self, token=token)

    def send_message(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        text: str,
        tenant_id: str = "",
        reply_markup: dict[str, Any] | None = None,
        callback_query_id: str | None = None,
        track_event_type: str | None = None,
        track_payload: dict[str, Any] | None = None,
        channel: str = "telegram",
        priority: Any = "normal",
        critical: bool = True,
        channel_policy: dict[str, Any] | None = None,
    ) -> Any:
        return send_message_effect(
            self,
            decision_id=decision_id,
            correlation_id=correlation_id,
            user_id=user_id,
            text=text,
            tenant_id=tenant_id,
            reply_markup=reply_markup,
            callback_query_id=callback_query_id,
            track_event_type=track_event_type,
            track_payload=track_payload,
            channel=channel,
            priority=priority,
            critical=critical,
            channel_policy=channel_policy,
        )

    def _telegram_send_message(
        self,
        *,
        chat_id: str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        priority: Any = "normal",
        critical: bool = True,
    ) -> tuple[bool, dict[str, Any]]:
        return send_message_transport_effect(
            self,
            chat_id=str(chat_id),
            text=str(text),
            reply_markup=reply_markup,
            priority=priority,
            critical=bool(critical),
        )

    def _telegram_send_chat_action(self, *, chat_id: str, action: str = "typing") -> None:
        return send_chat_action_effect(self, chat_id=str(chat_id), action=str(action or "typing"))

    def _telegram_answer_callback(
        self,
        callback_query_id: str,
        *,
        user_id: str,
        decision_id: str,
        correlation_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        answer_callback_internal_effect(
            self,
            callback_query_id=str(callback_query_id),
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            text=text,
            show_alert=show_alert,
        )

    def answer_callback(self, *, callback_query_id: str, text: str | None = None, show_alert: bool = False, **kwargs) -> dict:
        return answer_callback_public_effect(self, callback_query_id=callback_query_id, text=text, show_alert=show_alert, **kwargs)

    def answer_callback_query(self, *, callback_query_id: str, text: str | None = None, show_alert: bool = False, **kwargs) -> dict:
        return self.answer_callback(callback_query_id=callback_query_id, text=text, show_alert=show_alert, **kwargs)

    def poll_telegram_updates(self, *, token: str, offset: int | None = None, timeout: int = 30, limit: int = 100) -> dict:
        return poll_telegram_updates_effect(self, token=token, offset=offset, timeout=timeout, limit=limit)

    def send_audio(self, *args, **kwargs) -> Any:
        return send_audio_effect(self, *args, **kwargs)

    def send_message_transport(self, *args, **kwargs) -> Any:
        return send_message_transport_effect(self, *args, **kwargs)

    def send_audio_transport(self, *args, **kwargs) -> Any:
        return send_audio_transport_effect(self, *args, **kwargs)

    def send_chat_action(self, *args, **kwargs) -> Any:
        return send_chat_action_effect(self, *args, **kwargs)

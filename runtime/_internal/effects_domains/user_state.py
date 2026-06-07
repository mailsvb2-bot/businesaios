from __future__ import annotations

from typing import Any, Optional

from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


class UserStateEffectsMixin:
    """User state effects (event-sourced).

    Pure persistence as events, plus optional UX acknowledgement via send_message.
    """

    event_log: Any

    def set_user_setting(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        key: str,
        value: Any = None,
        notify_text: str | None = None,
        notify_reply_markup: dict[str, Any] | None = None,
        callback_query_id: str | None = None,
        channel: str = "telegram",
    ) -> Any:
        assert_called_from_executor()

        # UX: stop the spinner for inline buttons.
        if channel == "telegram" and isinstance(callback_query_id, str) and callback_query_id.strip():
            try:
                self._telegram_answer_callback(callback_query_id.strip())  # type: ignore[attr-defined]
            except Exception:
                swallow(__name__, 'runtime/_internal/effects_domains/user_state.py')

        self.event_log.emit(
            event_type="user_setting_set",
            source="user_state",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"key": str(key), "value": value},
        )

        if isinstance(notify_text, str) and notify_text.strip():
            return self.send_message(  # type: ignore[attr-defined]
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                user_id=str(user_id),
                text=str(notify_text)[:3500],
                reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                callback_query_id=str(callback_query_id) if callback_query_id else None,
                channel=str(channel),
            )

        return {"ok": True}

    def log_mood(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        score: int,
        note: str | None = None,
        notify_text: str | None = None,
        notify_reply_markup: dict[str, Any] | None = None,
        callback_query_id: str | None = None,
        channel: str = "telegram",
    ) -> Any:
        assert_called_from_executor()

        # UX: stop the spinner for inline buttons.
        if channel == "telegram" and isinstance(callback_query_id, str) and callback_query_id.strip():
            try:
                self._telegram_answer_callback(callback_query_id.strip())  # type: ignore[attr-defined]
            except Exception:
                swallow(__name__, 'runtime/_internal/effects_domains/user_state.py')

        try:
            score_i = int(score)
        except Exception:
            score_i = 0
        score_i = max(0, min(10, score_i))

        self.event_log.emit(
            event_type="mood_logged",
            source="user_state",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"score": int(score_i), "note": (str(note)[:2000] if note else "")},
        )

        if isinstance(notify_text, str) and notify_text.strip():
            return self.send_message(  # type: ignore[attr-defined]
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                user_id=str(user_id),
                text=str(notify_text)[:3500],
                reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                callback_query_id=str(callback_query_id) if callback_query_id else None,
                channel=str(channel),
            )

        return {"ok": True}

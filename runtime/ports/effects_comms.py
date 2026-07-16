from __future__ import annotations

from typing import Protocol

from runtime.ports.effects_types import Any, Dict, Optional


class EffectsCommsPort(Protocol):
    def send_message(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        text: str,
        tenant_id: str = "",
        reply_markup: Optional[Dict[str, Any]] = None,
        callback_query_id: Optional[str] = None,
        track_event_type: Optional[str] = None,
        track_payload: Optional[Dict[str, Any]] = None,
        channel: str = "telegram",
        priority: Any = "normal",
        critical: bool = True,
        channel_policy: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    def send_audio(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        path: str,
        kind: str = "voice",
        caption: str | None = None,
        callback_query_id: Optional[str] = None,
        channel: str = "telegram",
    ) -> Any: ...

    def send_weather(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        city: str,
        channel: str = "telegram",
        channel_policy: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    def track_event(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "tracking",
    ) -> Any: ...

    def answer_callback_query(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> Any: ...

    def poll_telegram_updates(
        self,
        *,
        offset: int | None = None,
        timeout_s: int = 20,
        limit: int = 50,
    ) -> Any: ...

    def telegram_self_check(self, *, token: str | None = None) -> Dict[str, Any]: ...

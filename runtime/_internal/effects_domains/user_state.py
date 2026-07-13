from __future__ import annotations

from typing import Any

from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def _ledger_evidence(*, decision_id: str, tenant_id: str, user_id: str, key: str, value: Any) -> dict[str, Any]:
    ref = f"user-setting:{tenant_id}:{decision_id}:{user_id}:{key}"
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": "user_setting_recorded",
        "external_refs": [ref],
        "confidence": 1.0,
        "payload": {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "key": str(key),
            "value": value,
        },
    }


class UserStateEffectsMixin:
    """Tenant-bound user state effects persisted through the canonical event log."""

    event_log: Any

    def set_user_setting(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        user_id: str,
        key: str,
        value: Any = None,
        notify_text: str | None = None,
        notify_reply_markup: dict[str, Any] | None = None,
        callback_query_id: str | None = None,
        channel: str = "telegram",
    ) -> Any:
        assert_called_from_executor()
        tenant = assert_event_log_tenant(
            self.event_log,
            tenant_id=str(tenant_id),
            operation="set_user_setting",
        )

        if channel == "telegram" and isinstance(callback_query_id, str) and callback_query_id.strip():
            try:
                self._telegram_answer_callback(  # type: ignore[attr-defined]
                    callback_query_id.strip(),
                    user_id=str(user_id),
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                )
            except Exception:
                swallow(__name__, "user_setting.answer_callback")

        payload = {
            "tenant_id": tenant,
            "key": str(key),
            "value": value,
        }
        self.event_log.emit(
            event_type="user_setting_set",
            source="user_state",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=payload,
        )
        evidence = _ledger_evidence(
            decision_id=str(decision_id),
            tenant_id=tenant,
            user_id=str(user_id),
            key=str(key),
            value=value,
        )

        notification: Any = None
        if isinstance(notify_text, str) and notify_text.strip():
            try:
                notification = self.send_message(  # type: ignore[attr-defined]
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    tenant_id=tenant,
                    user_id=str(user_id),
                    text=str(notify_text)[:3500],
                    reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                    callback_query_id=str(callback_query_id) if callback_query_id else None,
                    channel=str(channel),
                )
            except Exception as exc:
                notification = {"ok": False, "error": exc.__class__.__name__}

        return {
            "ok": True,
            "status": "verified",
            "setting": payload,
            "notification": notification,
            "router_evidence": evidence,
        }

from __future__ import annotations

from typing import Any

from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def _marketing_copy_evidence(*, decision_id: str, admin_id: str, step_key: str) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": "marketing_copy_recorded",
        "external_refs": [f"marketing-copy:{decision_id}:{admin_id}:{step_key}"],
        "confidence": 1.0,
        "payload": {"admin_id": str(admin_id), "step_key": str(step_key)},
    }


class MarketingEffectsMixin:
    """Marketing runtime hooks and governed copy storage."""

    event_log: Any

    def set_marketing_copy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        admin_id: str,
        step_key: str,
        variant_a: str,
        variant_b: str,
        notify_text: str | None = None,
        notify_reply_markup: dict[str, Any] | None = None,
        callback_query_id: str | None = None,
        channel: str = "telegram",
    ) -> Any:
        assert_called_from_executor()

        if channel == "telegram" and isinstance(callback_query_id, str) and callback_query_id.strip():
            try:
                self._telegram_answer_callback(  # type: ignore[attr-defined]
                    callback_query_id.strip(),
                    user_id=str(admin_id),
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                )
            except Exception:
                swallow(__name__, "marketing_copy.answer_callback")

        payload = {
            "step_key": str(step_key),
            "variant_a": str(variant_a)[:2000],
            "variant_b": str(variant_b)[:2000],
        }
        self.event_log.emit(
            event_type="marketing_copy_set",
            source="marketing",
            user_id=str(admin_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload=payload,
        )
        evidence = _marketing_copy_evidence(
            decision_id=str(decision_id),
            admin_id=str(admin_id),
            step_key=str(step_key),
        )

        notification: Any = None
        if isinstance(notify_text, str) and notify_text.strip():
            try:
                notification = self.send_message(  # type: ignore[attr-defined]
                    decision_id=str(decision_id),
                    correlation_id=str(correlation_id),
                    user_id=str(admin_id),
                    text=str(notify_text)[:3500],
                    reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                    callback_query_id=str(callback_query_id) if callback_query_id else None,
                    channel=str(channel),
                    priority="normal",
                    critical=False,
                )
            except Exception as exc:
                notification = {"ok": False, "error": exc.__class__.__name__}

        return {
            "ok": True,
            "status": "verified",
            "copy": payload,
            "notification": notification,
            "router_evidence": evidence,
        }

    def record_variant_shown(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        step_key: str,
        variant: str,
    ) -> Any:
        assert_called_from_executor()
        self.event_log.emit(
            event_type="variant_shown",
            source="marketing",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"step_key": str(step_key), "variant": str(variant)},
        )
        return {"ok": True}

    def record_variant_chosen(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        step_key: str,
        variant: str,
    ) -> Any:
        assert_called_from_executor()
        self.event_log.emit(
            event_type="variant_chosen",
            source="marketing",
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            payload={"step_key": str(step_key), "variant": str(variant)},
        )
        return {"ok": True}

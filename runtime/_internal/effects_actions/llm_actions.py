from __future__ import annotations

"""Sealed effect actions mixin.

This module is INTERNAL to runtime/_internal.
No API changes to EffectsPort.
"""

from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_actions.llm_completion_support import (
    emit_marketing_llm_error,
    emit_marketing_llm_success,
    read_provider_and_model,
)
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


class LLMEffectsMixin:
    def compose_marketing_message(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        prompt: str,
        system: str | None = None,
        admin_id: str | None = None,
        model: str | None = None,
        chat_id: int | None = None,
        reply_markup: dict | None = None,
        callback_query_id: str | None = None,
        track_event_type: str | None = None,
        track_payload: dict | None = None,
        priority: str | None = None,
        critical: bool = False,
        **_,
    ) -> dict:
        assert_called_from_executor()
        text = str(prompt or "").strip()
        try:
            out = self.marketing_llm_complete(
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                admin_id=str(admin_id or "system"),
                system=str(system or "You write concise marketing copy."),
                user=str(prompt),
                model=model,
            )
            if isinstance(out, dict) and out.get("ok") and str(out.get("text") or "").strip():
                text = str(out.get("text") or "").strip()
        except Exception:
            swallow(__name__, "runtime/_internal/_effects_impl.py")

        return self.send_message(
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            user_id=str(user_id),
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            callback_query_id=callback_query_id,
            track_event_type=track_event_type,
            track_payload=track_payload,
            priority=priority,
            critical=bool(critical),
        )

    def marketing_llm_complete(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        admin_id: str,
        system: str,
        user: str,
        model: str | None = None,
    ) -> dict:
        assert_called_from_executor()
        provider, configured_model = read_provider_and_model(provider_override=None, model_override=model)
        try:
            from runtime._internal.router_support import execute_effect_action_sync

            result = execute_effect_action_sync(
                self,
                EffectActionType.LLM_MARKETING_COMPLETE,
                {
                    "provider": provider,
                    "system": system,
                    "user": user,
                    "model": (model or configured_model),
                },
            )
            if result.get("ok"):
                try:
                    emit_marketing_llm_success(
                        event_log=self.event_log,
                        admin_id=admin_id,
                        decision_id=decision_id,
                        correlation_id=correlation_id,
                        provider=str(result.get("provider") or provider),
                        model=str(result.get("model") or model or ""),
                        text=str(result.get("text") or ""),
                    )
                except Exception:
                    swallow(__name__, "runtime/_internal/_effects_impl.py")
            return result
        except Exception as exc:
            try:
                emit_marketing_llm_error(
                    event_log=self.event_log,
                    admin_id=admin_id,
                    provider=provider,
                    model=str(model or ""),
                    error_name=type(exc).__name__,
                )
            except Exception:
                swallow(__name__, "runtime/_internal/_effects_impl.py")
            return {"ok": False, "provider": str(provider), "model": str(model or ""), "error": type(exc).__name__}

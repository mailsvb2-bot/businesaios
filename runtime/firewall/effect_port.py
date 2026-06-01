from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from runtime.firewall.process_guard import require_effect_capability
from runtime.tenancy import UNKNOWN_TENANT_ID, normalize_tenant_id


class EffectsPort(ABC):
    """EffectsPort (единая точка эффектов).

    Основной контракт — keyword-only (как runtime.ports.effects).
    Для тестов/совместимости GuardedEffects допускает и позиционные аргументы.
    """

    @abstractmethod
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
        ...

    @abstractmethod
    def capture_payment(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        amount: int,
        currency: str,
        provider: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        ...

    @abstractmethod
    def deploy_policy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        candidate_policy_id: str,
        rollout_pct: int,
    ) -> bool:
        ...

    @abstractmethod
    def rollback_policy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        reason: str,
    ) -> bool:
        ...


class GuardedEffects(EffectsPort):
    """Token-gated proxy over a real EffectsPort implementation."""

    def __init__(self, capability_token: str, impl: EffectsPort):
        self._token = capability_token
        self._impl = impl

    # NOTE: Accept *args for the explicit bypass test.
    def send_message(self, *args, **kwargs) -> Any:  # type: ignore[override]
        require_effect_capability(self._token)

        if args and not kwargs:
            # legacy / test call: (user_id, text)
            user_id, text = args[0], args[1]
            return self._impl.send_message(
                decision_id="unknown",
                correlation_id="unknown",
                user_id=str(user_id),
                text=str(text),
                tenant_id=UNKNOWN_TENANT_ID,
                channel="telegram",
            )

        return self._impl.send_message(
            decision_id=kwargs["decision_id"],
            correlation_id=kwargs["correlation_id"],
            user_id=kwargs["user_id"],
            text=kwargs["text"],
            tenant_id=(normalize_tenant_id(kwargs.get("tenant_id")) or normalize_tenant_id((kwargs.get("track_payload") or {}).get("tenant_id") if isinstance(kwargs.get("track_payload"), dict) else None) or UNKNOWN_TENANT_ID),
            reply_markup=kwargs.get("reply_markup"),
            callback_query_id=kwargs.get("callback_query_id"),
            track_event_type=kwargs.get("track_event_type"),
            track_payload=kwargs.get("track_payload"),
            channel=kwargs.get("channel", "telegram"),
            priority=kwargs.get("priority", "normal"),
            critical=kwargs.get("critical", True),
            channel_policy=kwargs.get("channel_policy"),
        )

    def capture_payment(self, **kwargs) -> Any:  # type: ignore[override]
        require_effect_capability(self._token)
        return self._impl.capture_payment(
            decision_id=kwargs["decision_id"],
            correlation_id=kwargs["correlation_id"],
            user_id=kwargs["user_id"],
            amount=int(kwargs["amount"]),
            currency=str(kwargs["currency"]),
            provider=str(kwargs["provider"]),
            metadata=kwargs.get("metadata"),
        )

    def deploy_policy(self, **kwargs) -> bool:  # type: ignore[override]
        require_effect_capability(self._token)
        return self._impl.deploy_policy(
            decision_id=kwargs["decision_id"],
            correlation_id=kwargs["correlation_id"],
            candidate_policy_id=str(kwargs["candidate_policy_id"]),
            rollout_pct=int(kwargs["rollout_pct"]),
        )

    def rollback_policy(self, **kwargs) -> bool:  # type: ignore[override]
        require_effect_capability(self._token)
        return self._impl.rollback_policy(
            decision_id=kwargs["decision_id"],
            correlation_id=kwargs["correlation_id"],
            reason=str(kwargs["reason"]),
        )

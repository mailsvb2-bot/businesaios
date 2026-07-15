from __future__ import annotations

from typing import Protocol

from runtime.ports.effects_types import Any, Dict, Optional


class EffectsRevenuePort(Protocol):
    def select_tariff(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        product_id: str,
        user_id: str,
        tariff: str,
        days: int,
        period: str,
        amount: int,
        plan_id: int | None = None,
        title: str | None = None,
        expected_price: int | None = None,
        notify_text: str | None = None,
        notify_reply_markup: Optional[Dict[str, Any]] = None,
        channel: str = "telegram",
        channel_policy: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    def capture_payment(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        amount: int,
        currency: str,
        provider: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    def reconcile_payments(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        window_min: int = 30,
    ) -> Any: ...

    def reconcile_payment(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        external_payment_id: str,
        notification_id: str | None = None,
        event: str | None = None,
        user_id_hint: str | None = None,
    ) -> Any: ...

    def grant_access(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        tenant_id: str,
        product_id: str,
        grant_key: str | None = None,
        full_access: bool = True,
        notify_text: str | None = None,
        notify_reply_markup: Optional[Dict[str, Any]] = None,
        track_event_type: str | None = None,
        track_payload: Optional[Dict[str, Any]] = None,
        channel: str = "telegram",
        channel_policy: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    def deploy_policy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        candidate_policy_id: str,
        rollout_pct: int,
    ) -> Any: ...

    def rollback_policy(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        tenant_id: str,
        reason: str,
    ) -> Any: ...

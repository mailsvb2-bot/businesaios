from __future__ import annotations

"""Sealed payment effect actions mixin.

Thin orchestration only; business details live in focused helper modules.
"""

from typing import Any, Dict, Optional, Tuple

from runtime._internal.effects_actions.payments.access import grant_access_effect
from runtime._internal.effects_actions.payments.reconciliation import (
    reconcile_payment_effect,
    reconcile_payments_effect,
)
from runtime._internal.effects_actions.payments.selection import (
    capture_payment_effect,
    select_tariff_effect,
)
from runtime._internal.effects_actions.payments.yookassa import (
    start_webhook_server,
    yookassa_create_payment,
    yookassa_get_payment_status,
)


class PaymentsEffectsMixin:
    def select_tariff(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        tariff: str,
        days: int,
        period: str,
        amount: int,
        plan_id: int | None = None,
        title: str | None = None,
        expected_price: int | None = None,
        notify_text: str | None = None,
        notify_reply_markup: dict[str, Any] | None = None,
    ) -> Any:
        return select_tariff_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            user_id=str(user_id),
            tariff=str(tariff),
            days=int(days),
            period=str(period),
            amount=int(amount),
            plan_id=plan_id,
            title=title,
            expected_price=expected_price,
            notify_text=notify_text,
            notify_reply_markup=notify_reply_markup,
        )

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
        return capture_payment_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            user_id=str(user_id),
            amount=int(amount),
            currency=str(currency),
            provider=str(provider),
            metadata=metadata,
        )

    def reconcile_payments(self, *, decision_id: str, correlation_id: str, window_min: int = 30) -> Any:
        return reconcile_payments_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            window_min=int(window_min),
        )

    def reconcile_payment(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        external_payment_id: str,
        notification_id: str | None = None,
        event: str | None = None,
        user_id_hint: str | None = None,
    ) -> bool:
        return reconcile_payment_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            external_payment_id=str(external_payment_id),
            notification_id=notification_id,
            event=event,
            user_id_hint=user_id_hint,
        )

    def grant_access(
        self,
        *,
        decision_id: str,
        correlation_id: str,
        user_id: str,
        tenant_id: str | None = None,
        product_id: str | None = None,
        grant_key: str | None = None,
        full_access: bool = True,
        notify_text: str | None = None,
        notify_reply_markup: dict | None = None,
        track_event_type: str | None = None,
        track_payload: dict | None = None,
    ) -> bool:
        return grant_access_effect(
            self,
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            user_id=str(user_id),
            tenant_id=tenant_id,
            product_id=product_id,
            grant_key=grant_key,
            full_access=bool(full_access),
            notify_text=notify_text,
            notify_reply_markup=notify_reply_markup,
            track_event_type=track_event_type,
            track_payload=track_payload,
        )

    def _yookassa_create_payment(
        self,
        *,
        decision_id: str,
        amount: int,
        currency: str,
        user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        return yookassa_create_payment(
            effects=self,
            decision_id=decision_id,
            amount=amount,
            currency=currency,
            user_id=user_id,
            metadata=metadata,
        )

    def _yookassa_get_payment_status(self, *, external_payment_id: str) -> str:
        return yookassa_get_payment_status(effects=self, external_payment_id=str(external_payment_id))

    def start_yookassa_webhook_server_in_thread(self, *, host: str, port: int, path: str, event_store: Any, payment_outbox: Any) -> Any:
        return start_webhook_server(host=host, port=port, path=path, event_store=event_store, payment_outbox=payment_outbox)

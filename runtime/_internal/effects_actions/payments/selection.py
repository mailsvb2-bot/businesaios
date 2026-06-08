from __future__ import annotations

from typing import Any, Optional

from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def select_tariff_effect(
    effects: Any,
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
) -> dict:
    assert_called_from_executor()
    payload: dict[str, Any] = {
        "tariff": str(tariff),
        "days": int(days),
        "period": str(period),
        "amount": int(amount),
    }
    if plan_id is not None:
        try:
            payload["plan_id"] = int(plan_id)
        except Exception:
            swallow(__name__, 'runtime/_internal/_effects_impl.py')
    if title:
        payload["title"] = str(title)[:128]
    if expected_price is not None:
        try:
            payload["expected_price"] = int(expected_price)
        except Exception:
            swallow(__name__, 'runtime/_internal/_effects_impl.py')

    effects.event_log.emit(
        event_type="tariff_selected",
        source="user_state",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=payload,
    )
    if notify_text:
        try:
            effects.send_message(
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                user_id=str(user_id),
                text=str(notify_text)[:3500],
                reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                channel="telegram",
            )
        except Exception:
            swallow(__name__, 'runtime/_internal/_effects_impl.py')
    return {"ok": True}


def capture_payment_effect(
    effects: Any,
    *,
    decision_id: str,
    correlation_id: str,
    user_id: str,
    amount: int,
    currency: str,
    provider: str,
    metadata: dict[str, Any] | None = None,
) -> dict:
    assert_called_from_executor()
    provider_norm = str(provider).lower().strip()
    if provider_norm in {"yookassa", "yoo", "yoo_kassa"}:
        ok, meta = effects._yookassa_create_payment(
            decision_id=str(decision_id),
            amount=int(amount),
            currency=str(currency),
            user_id=str(user_id),
            metadata=metadata or {},
        )
    else:
        ok, meta = False, {"provider": str(provider), "mode": "unsupported"}

    effects.event_log.emit(
        event_type="payment_captured",
        source="payments",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={"amount": int(amount), "currency": str(currency), "provider": str(provider), "ok": bool(ok), "meta": meta},
    )

    try:
        from core.payments.contracts import validate_payment_external_id

        ext_id = None
        if isinstance(meta, dict):
            ext_id = (meta or {}).get("yookassa", {}).get("id")
        if ok and provider_norm in {"yookassa", "yoo", "yoo_kassa"}:
            ext_id = validate_payment_external_id(str(ext_id or ""))
            effects.event_log.emit(
                event_type="payment_created",
                source="payments",
                user_id=str(user_id),
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload={
                    "external_id": str(ext_id),
                    "status": (meta or {}).get("yookassa", {}).get("status") if isinstance(meta, dict) else None,
                    "provider": "yookassa",
                },
            )
    except Exception as e:
        try:
            effects.event_log.emit(
                event_type="payment_create_failed",
                source="payments",
                user_id=str(user_id),
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload={"provider": str(provider), "reason": "missing_or_invalid_external_id", "error": str(e)[:500]},
            )
        except Exception:
            swallow(__name__, 'runtime/_internal/_effects_impl.py')
    return {"ok": bool(ok), "meta": meta}

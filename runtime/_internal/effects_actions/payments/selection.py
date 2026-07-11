from __future__ import annotations

from typing import Any

from runtime._internal.effect_types import EffectActionType
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def _payment_gateway_evidence(*, ok: bool, external_id: str | None, provider: str, meta: dict[str, Any]) -> dict[str, Any]:
    external_ref = str(external_id or "").strip()
    verified = bool(ok) and bool(external_ref)
    return {
        "source": "payment_gateway",
        "action_type": str(EffectActionType.PAYMENTS_YOOKASSA_CREATE),
        "verified": verified,
        "status": "verified" if verified else "failed",
        "summary": "payment_created" if verified else "payment_provider_confirmation_missing",
        "external_refs": [external_ref] if external_ref else [],
        "confidence": 1.0 if verified else 0.0,
        "payload": {
            "provider": str(provider),
            "provider_status": ((meta or {}).get("yookassa") or {}).get("status") if isinstance((meta or {}).get("yookassa"), dict) else None,
        },
    }


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
            swallow(__name__, "runtime/_internal/_effects_impl.py")
    if title:
        payload["title"] = str(title)[:128]
    if expected_price is not None:
        try:
            payload["expected_price"] = int(expected_price)
        except Exception:
            swallow(__name__, "runtime/_internal/_effects_impl.py")

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
            swallow(__name__, "runtime/_internal/_effects_impl.py")
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

    external_id: str | None = None
    try:
        from core.payments.contracts import validate_payment_external_id

        raw_external_id = None
        if isinstance(meta, dict):
            provider_payload = (meta or {}).get("yookassa")
            if isinstance(provider_payload, dict):
                raw_external_id = provider_payload.get("id")
        if ok and provider_norm in {"yookassa", "yoo", "yoo_kassa"}:
            external_id = validate_payment_external_id(str(raw_external_id or ""))
            effects.event_log.emit(
                event_type="payment_created",
                source="payments",
                user_id=str(user_id),
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload={
                    "external_id": str(external_id),
                    "status": (meta or {}).get("yookassa", {}).get("status") if isinstance(meta, dict) else None,
                    "provider": "yookassa",
                },
            )
    except Exception as exc:
        try:
            effects.event_log.emit(
                event_type="payment_create_failed",
                source="payments",
                user_id=str(user_id),
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                payload={"provider": str(provider), "reason": "missing_or_invalid_external_id", "error": str(exc)[:500]},
            )
        except Exception:
            swallow(__name__, "runtime/_internal/_effects_impl.py")

    return {
        "ok": bool(ok),
        "meta": meta,
        "evidence": _payment_gateway_evidence(
            ok=bool(ok),
            external_id=external_id,
            provider=provider_norm or str(provider),
            meta=dict(meta or {}),
        ),
    }


__all__ = ["capture_payment_effect", "select_tariff_effect"]

from __future__ import annotations

from typing import Any

from runtime._internal.effect_types import EffectActionType
from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def _business_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(metadata or {})
    return {
        key: data[key]
        for key in ("tenant_id", "product_id", "order_id")
        if str(data.get(key) or "").strip()
    }


def _ledger_evidence(*, code: str, external_ref: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": str(code),
        "external_refs": [str(external_ref)],
        "confidence": 1.0,
        "payload": dict(payload),
    }


def _payment_gateway_evidence(
    *,
    ok: bool,
    external_id: str | None,
    provider: str,
    meta: dict[str, Any],
    business_metadata: dict[str, Any],
) -> dict[str, Any]:
    external_ref = str(external_id or "").strip()
    verified = bool(ok) and bool(external_ref)
    provider_payload = (meta or {}).get("yookassa")
    provider_status = provider_payload.get("status") if isinstance(provider_payload, dict) else None
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
            "provider_status": provider_status,
            **dict(business_metadata),
        },
    }


def select_tariff_effect(
    effects: Any,
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
    notify_reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_called_from_executor()
    tenant = assert_event_log_tenant(
        effects.event_log,
        tenant_id=str(tenant_id or "").strip(),
        operation="select_tariff",
    )
    product = str(product_id or "").strip()
    user = str(user_id or "").strip()
    if not product:
        raise RuntimeError("PRODUCT_ID_REQUIRED")
    if not user:
        raise RuntimeError("USER_ID_REQUIRED")

    payload: dict[str, Any] = {
        "tenant_id": tenant,
        "product_id": product,
        "tariff": str(tariff),
        "days": int(days),
        "period": str(period),
        "amount": int(amount),
    }
    if plan_id is not None:
        payload["plan_id"] = int(plan_id)
    if title:
        payload["title"] = str(title)[:128]
    if expected_price is not None:
        payload["expected_price"] = int(expected_price)

    effects.event_log.emit(
        event_type="tariff_selected",
        source="user_state",
        user_id=user,
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload=payload,
    )
    evidence = _ledger_evidence(
        code="tariff_selection_recorded",
        external_ref=f"tariff:{tenant}:{product}:{user}:{decision_id}",
        payload=payload,
    )

    notification: Any = None
    if notify_text:
        try:
            notification = effects.send_message(
                decision_id=str(decision_id),
                correlation_id=str(correlation_id),
                tenant_id=tenant,
                user_id=user,
                text=str(notify_text)[:3500],
                reply_markup=notify_reply_markup if isinstance(notify_reply_markup, dict) else None,
                channel="telegram",
            )
        except Exception as exc:
            notification = {"ok": False, "error": exc.__class__.__name__}
    return {
        "ok": True,
        "status": "verified",
        "selection": payload,
        "notification": notification,
        "router_evidence": evidence,
    }


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
) -> dict[str, Any]:
    assert_called_from_executor()
    provider_norm = str(provider).lower().strip()
    payment_metadata = dict(metadata or {})
    causal_metadata = _business_metadata(payment_metadata)
    tenant = assert_event_log_tenant(
        effects.event_log,
        tenant_id=str(causal_metadata.get("tenant_id") or ""),
        operation="capture_payment",
    )
    causal_metadata["tenant_id"] = tenant

    if provider_norm in {"yookassa", "yoo", "yoo_kassa"}:
        ok, meta = effects._yookassa_create_payment(
            decision_id=str(decision_id),
            amount=int(amount),
            currency=str(currency),
            user_id=str(user_id),
            metadata=payment_metadata,
        )
    else:
        ok, meta = False, {"provider": str(provider), "mode": "unsupported"}

    effects.event_log.emit(
        event_type="payment_create_attempted",
        source="payments",
        user_id=str(user_id),
        decision_id=str(decision_id),
        correlation_id=str(correlation_id),
        payload={
            "amount": int(amount),
            "currency": str(currency),
            "provider": str(provider),
            "capture_requested": True,
            "ok": bool(ok),
            "metadata": causal_metadata,
            "meta": meta,
        },
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
                    "amount": int(amount),
                    "currency": str(currency),
                    "metadata": causal_metadata,
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
                payload={
                    "provider": str(provider),
                    "reason": "missing_or_invalid_external_id",
                    "error": str(exc)[:500],
                    "metadata": causal_metadata,
                },
            )
        except Exception:
            swallow(__name__, "runtime/_internal/effects_actions/payments/selection.py")

    return {
        "ok": bool(ok),
        "meta": meta,
        "evidence": _payment_gateway_evidence(
            ok=bool(ok),
            external_id=external_id,
            provider=provider_norm or str(provider),
            meta=dict(meta or {}),
            business_metadata=causal_metadata,
        ),
    }


__all__ = ["capture_payment_effect", "select_tariff_effect"]

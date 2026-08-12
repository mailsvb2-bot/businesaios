from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from billing.payment_provider_adapter_impl import RoutingPaymentProviderAdapter
from billing.payment_provider_capability import PaymentProviderCapabilities
from billing.payment_provider_contract import PaymentCheckoutRequest, PaymentCheckoutSession
from billing.payment_provider_registry import PaymentProviderRegistration, PaymentProviderRegistry
from billing.payment_provider_router import PaymentProviderRouter
from core.payments.provider import idempotence_key_for_order
from runtime._internal.effects_tenant import assert_event_log_tenant
from runtime.observability.error_handling import swallow
from runtime.security.runtime_asserts import assert_called_from_executor


def _business_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(metadata or {})
    return {key: data[key] for key in ("tenant_id", "product_id", "order_id") if str(data.get(key) or "").strip()}


def _required_business_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    observed = _business_metadata(metadata)
    required = {field: str(observed.get(field) or "").strip() for field in ("tenant_id", "product_id", "order_id")}
    missing = next((field for field, value in required.items() if not value), None)
    if missing:
        raise RuntimeError(f"{missing.upper()}_REQUIRED")
    return required


def _ledger_evidence(*, code: str, external_ref: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"source": "ledger", "verified": True, "status": "verified", "code": str(code), "external_refs": [str(external_ref)], "confidence": 1.0, "payload": dict(payload)}


def _payment_gateway_evidence(*, ok: bool, external_id: str | None, provider: str, meta: dict[str, Any], business_metadata: dict[str, Any], provider_status: str | None = None) -> dict[str, Any]:
    external_ref = str(external_id or "").strip()
    verified = bool(ok and external_ref)
    raw = (meta or {}).get(str(provider))
    observed_status = provider_status or (raw.get("status") if isinstance(raw, dict) else None)
    return {
        "source": "payment_gateway",
        "action_type": "payments.checkout",
        "verified": verified,
        "status": "verified" if verified else "failed",
        "summary": "payment_created" if verified else "payment_provider_confirmation_missing",
        "external_refs": [external_ref] if external_ref else [],
        "confidence": 1.0 if verified else 0.0,
        "payload": {"provider": str(provider), "provider_status": observed_status, **dict(business_metadata)},
    }


class _YooKassaCheckoutProvider:
    def __init__(self, effects: Any) -> None:
        self._effects = effects

    def provider_name(self) -> str:
        return "yookassa"

    def create_checkout(self, request: PaymentCheckoutRequest) -> PaymentCheckoutSession:
        normalized = request.normalized_copy()
        metadata = dict(normalized.metadata)
        ok, raw = self._effects._yookassa_create_payment(
            decision_id=str(metadata.get("decision_id") or normalized.idempotency_key),
            amount=normalized.amount_minor,
            currency=normalized.currency,
            user_id=normalized.customer_reference,
            metadata=metadata,
        )
        provider_payload = raw.get("yookassa") if isinstance(raw, Mapping) else None
        if not ok or not isinstance(provider_payload, Mapping):
            raise RuntimeError("yookassa checkout creation failed")
        return PaymentCheckoutSession(
            tenant_id=normalized.tenant_id,
            provider_name="yookassa",
            external_reference=str(provider_payload.get("id") or ""),
            checkout_url=str(provider_payload.get("confirmation_url") or ""),
            status=str(provider_payload.get("status") or ""),
            amount_minor=normalized.amount_minor,
            currency=normalized.currency,
            metadata={"legacy_meta": dict(raw)},
        ).normalized_copy()

    def get_payment_status(self, *, tenant_id: str, currency: str, provider_name: str, external_reference: str) -> str:
        del tenant_id, currency, provider_name
        return str(self._effects._yookassa_get_payment_status(external_payment_id=str(external_reference)))


def _checkout_adapter(effects: Any) -> RoutingPaymentProviderAdapter:
    current = getattr(effects, "payment_provider_adapter", None)
    if current is not None:
        return current
    registry = PaymentProviderRegistry((PaymentProviderRegistration(
        provider_name="yookassa",
        provider=_YooKassaCheckoutProvider(effects),
        currencies=("RUB",),
        capabilities=PaymentProviderCapabilities(operations=("checkout", "status")),
        backend_key="runtime_yookassa",
    ),))
    current = RoutingPaymentProviderAdapter(router=PaymentProviderRouter(registry=registry), registry=registry)
    effects.payment_provider_adapter = current
    return current


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
    channel: str = "telegram",
    channel_policy: dict[str, Any] | None = None,
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
                channel=str(channel),
                channel_policy=(
                    dict(channel_policy)
                    if isinstance(channel_policy, dict)
                    else None
                ),
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
    payment_metadata = dict(metadata or {})
    causal_metadata = _required_business_metadata(payment_metadata)
    tenant = assert_event_log_tenant(effects.event_log, tenant_id=causal_metadata["tenant_id"], operation="capture_payment")
    causal_metadata["tenant_id"] = tenant
    payment_metadata.update(causal_metadata)
    provider_hint = str(provider or "").strip().lower()
    if provider_hint in {"yoo", "yoo_kassa"}:
        provider_hint = "yookassa"
    session: PaymentCheckoutSession | None = None
    meta: dict[str, Any]
    try:
        request = PaymentCheckoutRequest(
            tenant_id=tenant,
            amount_minor=int(amount),
            currency=str(currency),
            idempotency_key=idempotence_key_for_order(causal_metadata["order_id"]),
            customer_reference=str(user_id),
            description=str(payment_metadata.get("description") or "Payment"),
            metadata={**payment_metadata, "decision_id": str(decision_id), "provider_name_hint": provider_hint},
        )
        session = _checkout_adapter(effects).create_checkout(request)
        legacy_meta = session.metadata.get("legacy_meta")
        meta = dict(legacy_meta) if isinstance(legacy_meta, Mapping) else {session.provider_name: {"id": session.external_reference, "status": session.status, "confirmation_url": session.checkout_url}}
        provider_ok = True
    except Exception as exc:
        provider_ok = False
        meta = {"provider": str(provider), "mode": "unsupported" if isinstance(exc, LookupError) else "failed", "error": type(exc).__name__}
    effects.event_log.emit(
        event_type="payment_create_attempted", source="payments", user_id=str(user_id),
        decision_id=str(decision_id), correlation_id=str(correlation_id),
        payload={"amount": int(amount), "currency": str(currency), "provider": str(provider), "capture_requested": True, "ok": provider_ok, "metadata": causal_metadata, "meta": meta},
    )
    if session is None:
        effects.event_log.emit(
            event_type="payment_create_failed", source="payments", user_id=str(user_id),
            decision_id=str(decision_id), correlation_id=str(correlation_id),
            payload={"provider": str(provider), "reason": "checkout_unavailable", "error": str(meta.get("error") or "")[:500], "metadata": causal_metadata},
        )
    external_id: str | None = None
    if session is not None:
        try:
            from core.payments.contracts import validate_payment_external_id
            external_id = validate_payment_external_id(session.external_reference)
            effects.event_log.emit(
                event_type="payment_created", source="payments", user_id=str(user_id),
                decision_id=str(decision_id), correlation_id=str(correlation_id),
                payload={"external_id": external_id, "status": session.status, "provider": session.provider_name, "amount": int(amount), "currency": str(currency), "metadata": causal_metadata},
            )
        except Exception as exc:
            external_id = None
            try:
                effects.event_log.emit(
                    event_type="payment_create_failed", source="payments", user_id=str(user_id),
                    decision_id=str(decision_id), correlation_id=str(correlation_id),
                    payload={"provider": str(provider), "reason": "missing_or_invalid_external_id", "error": str(exc)[:500], "metadata": causal_metadata},
                )
            except Exception:
                swallow(__name__, "runtime/_internal/effects_actions/payments/selection.py")
    verified = bool(provider_ok and external_id and session)
    evidence = _payment_gateway_evidence(
        ok=verified, external_id=external_id, provider=session.provider_name if session else provider_hint or str(provider),
        meta=meta, business_metadata=causal_metadata, provider_status=session.status if session else None,
    )
    checkout = None if not verified or session is None else {"provider": session.provider_name, "external_id": external_id, "status": session.status, "checkout_url": session.checkout_url}
    return {"ok": verified, "status": "verified" if verified else "failed", "checkout": checkout, "meta": meta, "evidence": evidence, "router_evidence": evidence if verified else None}


__all__ = ["capture_payment_effect", "select_tariff_effect"]
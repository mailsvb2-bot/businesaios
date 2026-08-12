from __future__ import annotations

from datetime import UTC, datetime

import pytest

from billing.payment_provider_adapter import RoutingPaymentProviderAdapter
from billing.payment_provider_capability import PaymentProviderCapabilities
from billing.payment_provider_contract import PaymentCheckoutRequest, PaymentCheckoutSession
from billing.payment_provider_registry import PaymentProviderRegistration, PaymentProviderRegistry
from billing.payment_provider_router import PaymentProviderRouter
from runtime._internal.effects_actions.payments import selection as selection_module
from runtime._internal.effects_actions.payments.selection import capture_payment_effect

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _Provider:
    def __init__(self, name: str) -> None:
        self.name = name

    def provider_name(self) -> str:
        return self.name

    def ensure_customer(self, **_kwargs):
        raise NotImplementedError

    def collect(self, _attempt):
        raise NotImplementedError

    def refund(self, **_kwargs):
        raise NotImplementedError


class _EventLog:
    tenant_id = "business-a"

    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, **event) -> None:
        self.events.append(dict(event))


class _RuntimeEffects:
    def __init__(self, provider_result=(False, {})) -> None:
        self.event_log = _EventLog()
        self.provider_result = provider_result

    def _yookassa_create_payment(self, **_kwargs):
        return self.provider_result


def _request(*, currency: str = "RUB") -> PaymentCheckoutRequest:
    return PaymentCheckoutRequest(
        tenant_id="tenant-a",
        amount_minor=199000,
        currency=currency,
        idempotency_key="order:42",
        customer_reference="user-42",
    )


def test_checkout_capability_requires_real_provider_implementation() -> None:
    with pytest.raises(ValueError, match="does not implement advertised operation: checkout"):
        PaymentProviderRegistration(
            provider_name="alpha",
            provider=_Provider("alpha"),
            currencies=("RUB",),
            capabilities=PaymentProviderCapabilities(operations=("checkout",)),
        ).validate()


def test_checkout_routes_through_registry_router_and_adapter() -> None:
    class CheckoutProvider(_Provider):
        def __init__(self, name: str) -> None:
            super().__init__(name)
            self.requests = []

        def create_checkout(self, request):
            self.requests.append(request)
            return PaymentCheckoutSession(
                tenant_id=request.tenant_id,
                provider_name=self.name,
                external_reference="alpha-payment-1",
                checkout_url="https://alpha.example/pay/1",
                status="pending",
                amount_minor=request.amount_minor,
                currency=request.currency,
            )

    provider = CheckoutProvider("alpha")
    registry = PaymentProviderRegistry((PaymentProviderRegistration(
        provider_name="alpha",
        provider=provider,
        currencies=("RUB",),
        capabilities=PaymentProviderCapabilities(operations=("checkout",)),
        backend_key="alpha_redirect",
    ),))
    adapter = RoutingPaymentProviderAdapter(registry=registry, router=PaymentProviderRouter(registry=registry))
    result = adapter.create_checkout(_request(currency="rub"))

    assert result.provider_name == "alpha"
    assert result.checkout_url == "https://alpha.example/pay/1"
    assert result.currency == "RUB"
    assert result.metadata["routed_provider"] == "alpha"
    assert result.metadata["provider_backend_key"] == "alpha_redirect"
    assert provider.requests[0].metadata["owner"] == "billing.payment_provider_adapter"


def test_bad_checkout_binding_marks_provider_unhealthy() -> None:
    class BadProvider(_Provider):
        def create_checkout(self, request):
            return PaymentCheckoutSession(
                tenant_id="other-tenant",
                provider_name=self.name,
                external_reference="bad-1",
                checkout_url="https://bad.example/pay",
                status="pending",
                amount_minor=request.amount_minor,
                currency=request.currency,
            )

    registry = PaymentProviderRegistry((PaymentProviderRegistration(
        provider_name="bad",
        provider=BadProvider("bad"),
        currencies=("RUB",),
        capabilities=PaymentProviderCapabilities(operations=("checkout",)),
    ),))
    router = PaymentProviderRouter(registry=registry)
    adapter = RoutingPaymentProviderAdapter(registry=registry, router=router)
    with pytest.raises(RuntimeError, match="failed checkout"):
        adapter.create_checkout(_request())
    with pytest.raises(LookupError, match="no payment provider"):
        router.route_payment_provider(tenant_id="tenant-a", currency="RUB", operation="checkout", now=NOW)


def test_yookassa_is_normalized_to_canonical_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "assert_called_from_executor", lambda: None)
    effects = _RuntimeEffects((True, {"yookassa": {"id": "payment-42", "status": "pending", "confirmation_url": "https://pay.example/42"}}))
    result = capture_payment_effect(
        effects,
        decision_id="decision-payment",
        correlation_id="correlation-payment",
        user_id="user-1",
        amount=1500,
        currency="RUB",
        provider="yoo_kassa",
        metadata={"tenant_id": "business-a", "product_id": "crm-pro", "order_id": "order-42"},
    )
    assert result["checkout"] == {"provider": "yookassa", "external_id": "payment-42", "status": "pending", "checkout_url": "https://pay.example/42"}
    assert [event["event_type"] for event in effects.event_log.events] == ["payment_create_attempted", "payment_created"]
    assert all(event["event_type"] != "payment_captured" for event in effects.event_log.events)


def test_injected_provider_uses_same_runtime_payment_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selection_module, "assert_called_from_executor", lambda: None)

    class StripeProvider:
        def provider_name(self) -> str:
            return "stripe"

        def create_checkout(self, request):
            return PaymentCheckoutSession(
                tenant_id=request.tenant_id,
                provider_name="stripe",
                external_reference="cs_test_42",
                checkout_url="https://checkout.stripe.example/cs_test_42",
                status="open",
                amount_minor=request.amount_minor,
                currency=request.currency,
            )

    registry = PaymentProviderRegistry((PaymentProviderRegistration(
        provider_name="stripe",
        provider=StripeProvider(),
        currencies=("EUR",),
        capabilities=PaymentProviderCapabilities(operations=("checkout",)),
        backend_key="stripe_redirect",
    ),))
    effects = _RuntimeEffects()
    effects.payment_provider_adapter = RoutingPaymentProviderAdapter(registry=registry, router=PaymentProviderRouter(registry=registry))
    result = capture_payment_effect(
        effects,
        decision_id="decision-stripe",
        correlation_id="correlation-stripe",
        user_id="user-1",
        amount=2500,
        currency="EUR",
        provider="stripe",
        metadata={"tenant_id": "business-a", "product_id": "crm-pro", "order_id": "order-stripe"},
    )
    assert result["ok"] is True
    assert result["checkout"]["provider"] == "stripe"
    assert result["checkout"]["checkout_url"] == "https://checkout.stripe.example/cs_test_42"
    assert result["evidence"]["payload"]["provider"] == "stripe"

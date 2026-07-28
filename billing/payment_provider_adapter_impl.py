from __future__ import annotations

from billing.payment_provider_adapter_customer import PaymentProviderCustomerMixin
from billing.payment_provider_adapter_helpers import PaymentProviderRoutingMixin
from billing.payment_provider_adapter_money import PaymentProviderMoneyMixin
from billing.payment_provider_contract import PaymentProviderContract
from billing.payment_provider_registry import PaymentProviderRegistry
from billing.payment_provider_router import PaymentProviderRouter


CANON_BILLING_PAYMENT_PROVIDER_ADAPTER = True
CANON_BILLING_PAYMENT_PROVIDER_ADAPTER_DECOMPOSED = True


class RoutingPaymentProviderAdapter(
    PaymentProviderCustomerMixin,
    PaymentProviderMoneyMixin,
    PaymentProviderRoutingMixin,
    PaymentProviderContract,
):
    """Route billing operations through one canonical provider boundary.

    Customer provisioning may fail over only with a deterministic idempotency
    key. Money-moving collect/refund calls are never retried after dispatch.
    """

    def __init__(self, *, router: PaymentProviderRouter, registry: PaymentProviderRegistry) -> None:
        if not isinstance(router, PaymentProviderRouter):
            raise ValueError("router must be PaymentProviderRouter")
        if not isinstance(registry, PaymentProviderRegistry):
            raise ValueError("registry must be PaymentProviderRegistry")
        self._router = router
        self._registry = registry

    def provider_name(self) -> str:
        return "routed"


__all__ = [
    "CANON_BILLING_PAYMENT_PROVIDER_ADAPTER",
    "CANON_BILLING_PAYMENT_PROVIDER_ADAPTER_DECOMPOSED",
    "RoutingPaymentProviderAdapter",
]

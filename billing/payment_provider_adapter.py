"""Stable public import for the canonical routed payment provider adapter."""

from billing.payment_provider_adapter_impl import (
    CANON_BILLING_PAYMENT_PROVIDER_ADAPTER,
    CANON_BILLING_PAYMENT_PROVIDER_ADAPTER_DECOMPOSED,
    RoutingPaymentProviderAdapter,
)


__all__ = [
    "CANON_BILLING_PAYMENT_PROVIDER_ADAPTER",
    "CANON_BILLING_PAYMENT_PROVIDER_ADAPTER_DECOMPOSED",
    "RoutingPaymentProviderAdapter",
]

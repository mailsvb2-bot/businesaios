from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping, Protocol

from billing.commercial_cycle_contract import (
    CommercialCollectionAttempt,
    CommercialCollectionResult,
    require_commercial_int,
)
from core.tenancy.normalization import require_tenant_id

CANON_BILLING_PAYMENT_PROVIDER_CONTRACT = True


def _text(name: str, value: object) -> str:
    value = str(value or '').strip()
    if not value:
        raise ValueError(f'{name} is required')
    return value


def _checkout_common(tenant_id: str, amount_minor: int, currency: str, metadata: Mapping[str, object]) -> tuple[str, int, str, dict[str, object]]:
    if not isinstance(metadata, Mapping):
        raise ValueError('metadata must be a mapping')
    return require_tenant_id(tenant_id), require_commercial_int('amount_minor', amount_minor, minimum=1), _text('currency', currency).upper(), dict(metadata)


@dataclass(frozen=True)
class PaymentCustomerProfile:
    tenant_id: str
    provider_customer_id: str
    default_currency: str = 'USD'
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        all((require_tenant_id(self.tenant_id), _text('provider_customer_id', self.provider_customer_id), _text('default_currency', self.default_currency)))

    def normalized_copy(self) -> 'PaymentCustomerProfile':
        self.validate()
        return replace(self, tenant_id=require_tenant_id(self.tenant_id), provider_customer_id=str(self.provider_customer_id).strip(), default_currency=str(self.default_currency).strip().upper(), metadata=dict(self.metadata))


@dataclass(frozen=True)
class PaymentCheckoutRequest:
    tenant_id: str
    amount_minor: int
    currency: str
    idempotency_key: str
    customer_reference: str = ''
    description: str = 'Payment'
    metadata: Mapping[str, object] = field(default_factory=dict)

    def normalized_copy(self) -> 'PaymentCheckoutRequest':
        tenant, amount, currency, metadata = _checkout_common(self.tenant_id, self.amount_minor, self.currency, self.metadata)
        return replace(self, tenant_id=tenant, amount_minor=amount, currency=currency, idempotency_key=_text('idempotency_key', self.idempotency_key), customer_reference=str(self.customer_reference or '').strip(), description=str(self.description or 'Payment').strip() or 'Payment', metadata=metadata)


@dataclass(frozen=True)
class PaymentCheckoutSession:
    tenant_id: str
    provider_name: str
    external_reference: str
    checkout_url: str
    status: str
    amount_minor: int
    currency: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def normalized_copy(self) -> 'PaymentCheckoutSession':
        tenant, amount, currency, metadata = _checkout_common(self.tenant_id, self.amount_minor, self.currency, self.metadata)
        return replace(self, tenant_id=tenant, provider_name=_text('provider_name', self.provider_name), external_reference=_text('external_reference', self.external_reference), checkout_url=_text('checkout_url', self.checkout_url), status=_text('status', self.status), amount_minor=amount, currency=currency, metadata=metadata)


class PaymentProviderContract(Protocol):
    def provider_name(self) -> str: ...
    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata: Mapping[str, object] | None = None) -> PaymentCustomerProfile: ...
    def create_checkout(self, request: PaymentCheckoutRequest) -> PaymentCheckoutSession: ...
    def get_payment_status(self, *, tenant_id: str, currency: str, provider_name: str, external_reference: str) -> str: ...
    def collect(self, attempt: CommercialCollectionAttempt) -> CommercialCollectionResult: ...
    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata: Mapping[str, object] | None = None) -> Mapping[str, object]: ...


__all__ = ['CANON_BILLING_PAYMENT_PROVIDER_CONTRACT', 'PaymentCheckoutRequest', 'PaymentCheckoutSession', 'PaymentCustomerProfile', 'PaymentProviderContract']
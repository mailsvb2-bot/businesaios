from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping, Protocol

from core.tenancy.normalization import require_tenant_id

from billing.commercial_cycle_contract import CommercialCollectionAttempt, CommercialCollectionResult


CANON_BILLING_PAYMENT_PROVIDER_CONTRACT = True


@dataclass(frozen=True)
class PaymentCustomerProfile:
    tenant_id: str
    provider_customer_id: str
    default_currency: str = 'USD'
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.provider_customer_id or '').strip():
            raise ValueError('provider_customer_id is required')
        if not str(self.default_currency or '').strip():
            raise ValueError('default_currency is required')

    def normalized_copy(self) -> 'PaymentCustomerProfile':
        self.validate()
        return replace(
            self,
            tenant_id=require_tenant_id(self.tenant_id),
            provider_customer_id=str(self.provider_customer_id).strip(),
            default_currency=str(self.default_currency).strip().upper(),
            metadata=dict(self.metadata),
        )


class PaymentProviderContract(Protocol):
    def provider_name(self) -> str: ...
    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata: Mapping[str, object] | None = None) -> PaymentCustomerProfile: ...
    def collect(self, attempt: CommercialCollectionAttempt) -> CommercialCollectionResult: ...
    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata: Mapping[str, object] | None = None) -> Mapping[str, object]: ...


__all__ = ['CANON_BILLING_PAYMENT_PROVIDER_CONTRACT', 'PaymentCustomerProfile', 'PaymentProviderContract']

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable, Mapping

from billing.payment_provider_capability import PaymentProviderCapabilities
from billing.payment_provider_contract import PaymentProviderContract


CANON_BILLING_PAYMENT_PROVIDER_REGISTRY = True


@dataclass(frozen=True)
class PaymentProviderRegistration:
    provider_name: str
    provider: PaymentProviderContract
    currencies: tuple[str, ...] = ()
    priority: int = 100
    tenant_allowlist: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    capabilities: PaymentProviderCapabilities = field(default_factory=PaymentProviderCapabilities)
    backend_key: str = 'generic'

    def validate(self) -> None:
        if not str(self.provider_name or '').strip():
            raise ValueError('provider_name is required')
        if str(self.provider.provider_name()).strip().lower() != str(self.provider_name).strip().lower():
            raise ValueError('provider_name must match provider.provider_name()')
        if int(self.priority) < 0:
            raise ValueError('priority must be >= 0')
        normalized_currencies = tuple(str(item).strip().upper() for item in self.currencies)
        if any(not item for item in normalized_currencies):
            raise ValueError('currencies cannot contain blank values')
        if len(set(normalized_currencies)) != len(normalized_currencies):
            raise ValueError('currencies must be unique')
        self.capabilities.validate()
        if not str(self.backend_key or '').strip():
            raise ValueError('backend_key is required')
        normalized_tenants = tuple(str(item).strip() for item in self.tenant_allowlist)
        if any(not item for item in normalized_tenants):
            raise ValueError('tenant_allowlist cannot contain blank values')
        if len(set(normalized_tenants)) != len(normalized_tenants):
            raise ValueError('tenant_allowlist must be unique')

    def normalized_copy(self) -> 'PaymentProviderRegistration':
        self.validate()
        return replace(
            self,
            provider_name=str(self.provider_name).strip(),
            currencies=tuple(sorted({str(item).strip().upper() for item in self.currencies})),
            tenant_allowlist=tuple(sorted({str(item).strip() for item in self.tenant_allowlist})),
            priority=int(self.priority),
            metadata=dict(self.metadata),
            capabilities=self.capabilities.normalized_copy(),
            backend_key=str(self.backend_key).strip().lower(),
        )


    def supports_operation(self, *, operation: str, metadata: Mapping[str, object] | None = None) -> bool:
        normalized = self.normalized_copy()
        if not normalized.capabilities.supports(operation):
            return False
        md = dict(metadata or {})
        if str(operation or '').strip().lower() == 'refund' and bool(md.get('strict_provider_affinity')) and not bool(normalized.capabilities.strict_affinity_for_refund):
            preferred = str(md.get('preferred_provider') or md.get('provider_name_hint') or '').strip()
            provider_customer_id = str(md.get('provider_customer_id') or '').strip()
            affinity = preferred or (provider_customer_id.split(':', 1)[0].strip() if ':' in provider_customer_id else '')
            if affinity and affinity.lower() == str(normalized.provider_name).strip().lower():
                return True
            if affinity:
                return False
        return True

    def supports(self, *, tenant_id: str, currency: str) -> bool:
        normalized = self.normalized_copy()
        tenant = str(tenant_id or '').strip()
        normalized_currency = str(currency or '').strip().upper()
        if not tenant:
            raise ValueError('tenant_id is required')
        if not normalized_currency:
            raise ValueError('currency is required')
        if normalized.tenant_allowlist and tenant not in set(normalized.tenant_allowlist):
            return False
        if normalized.currencies and normalized_currency not in set(normalized.currencies):
            return False
        return True


class PaymentProviderRegistry:
    def __init__(self, registrations: Iterable[PaymentProviderRegistration] | None = None) -> None:
        self._registrations: dict[str, PaymentProviderRegistration] = {}
        for registration in registrations or ():
            self.register(registration)

    def register(self, registration: PaymentProviderRegistration) -> PaymentProviderRegistration:
        normalized = registration.normalized_copy()
        key = str(normalized.provider_name).strip().lower()
        existing = self._registrations.get(key)
        if existing is not None and existing != normalized:
            raise ValueError(f'provider {normalized.provider_name} already registered with different configuration')
        self._registrations[key] = normalized
        return normalized

    def get(self, provider_name: str) -> PaymentProviderRegistration:
        key = str(provider_name or '').strip().lower()
        if not key:
            raise ValueError('provider_name is required')
        try:
            return self._registrations[key]
        except KeyError as exc:
            raise LookupError(f'unknown provider: {provider_name}') from exc

    def list_registrations(self) -> tuple[PaymentProviderRegistration, ...]:
        return tuple(sorted((item.normalized_copy() for item in self._registrations.values()), key=lambda item: (int(item.priority), str(item.provider_name).lower())))


__all__ = ['CANON_BILLING_PAYMENT_PROVIDER_REGISTRY', 'PaymentProviderRegistration', 'PaymentProviderRegistry']

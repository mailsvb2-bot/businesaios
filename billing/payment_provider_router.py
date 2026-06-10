from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from billing.commercial_cycle_contract import utc_now
from billing.payment_provider_contract import PaymentProviderContract
from billing.payment_provider_health_registry import PaymentProviderHealthRegistry
from billing.payment_provider_registry import PaymentProviderRegistry

CANON_BILLING_PAYMENT_PROVIDER_ROUTER = True


@dataclass(frozen=True)
class PaymentProviderSelection:
    tenant_id: str
    currency: str
    provider_name: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.tenant_id or '').strip():
            raise ValueError('tenant_id is required')
        if not str(self.currency or '').strip():
            raise ValueError('currency is required')
        if not str(self.provider_name or '').strip():
            raise ValueError('provider_name is required')


class PaymentProviderRouter:
    def __init__(self, *, registry: PaymentProviderRegistry, health_registry: PaymentProviderHealthRegistry | None = None) -> None:
        self._registry = registry
        self._health = health_registry or PaymentProviderHealthRegistry()

    def list_candidates(self, *, tenant_id: str, currency: str, operation: str | None = None, metadata: Mapping[str, object] | None = None, now=None) -> tuple[PaymentProviderSelection, ...]:
        tenant = str(tenant_id or '').strip()
        normalized_currency = str(currency or '').strip().upper()
        if not tenant:
            raise ValueError('tenant_id is required')
        if not normalized_currency:
            raise ValueError('currency is required')
        now = now or utc_now()
        if now.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        candidates: list[tuple[int, int, str, str, object, object]] = []
        normalized_operation = None if operation is None else str(operation).strip().lower()
        candidate_metadata = dict(metadata or {})
        for registration in self._registry.list_registrations():
            if not registration.supports(tenant_id=tenant, currency=normalized_currency):
                continue
            if normalized_operation is not None and not registration.supports_operation(operation=normalized_operation, metadata=candidate_metadata):
                continue
            if not self._health.is_available(registration.provider_name, now=now):
                continue
            health = self._health.get(registration.provider_name)
            cooldown_sort = '' if health.cooldown_until is None else health.cooldown_until.isoformat()
            candidates.append((int(registration.priority), int(health.failure_count), cooldown_sort, str(registration.provider_name).lower(), registration, health))
        ordered: list[PaymentProviderSelection] = []
        for _, failure_count, _, _, selected, health in sorted(candidates, key=lambda item: (item[0], item[1], item[2], item[3])):
            result = PaymentProviderSelection(
                tenant_id=tenant,
                currency=normalized_currency,
                provider_name=selected.provider_name,
                metadata={
                    'owner': 'billing.payment_provider_router',
                    'priority': selected.priority,
                    'failure_count': failure_count,
                    'cooldown_until': None if health.cooldown_until is None else health.cooldown_until.isoformat(),
                    'operation': normalized_operation,
                    'backend_key': selected.backend_key,
                },
            )
            result.validate()
            ordered.append(result)
        return tuple(ordered)

    def route_payment_provider(self, *, tenant_id: str, currency: str, operation: str | None = None, metadata: Mapping[str, object] | None = None, now=None) -> PaymentProviderSelection:
        candidates = self.list_candidates(tenant_id=tenant_id, currency=currency, operation=operation, metadata=metadata, now=now)
        if not candidates:
            tenant = str(tenant_id or '').strip()
            normalized_currency = str(currency or '').strip().upper()
            raise LookupError(f'no payment provider available for tenant={tenant} currency={normalized_currency}')
        return candidates[0]

    def resolve_provider(self, *, tenant_id: str, currency: str, operation: str | None = None, metadata: Mapping[str, object] | None = None, now=None) -> PaymentProviderContract:
        selection = self.route_payment_provider(tenant_id=tenant_id, currency=currency, operation=operation, metadata=metadata, now=now)
        return self._registry.get(selection.provider_name).provider

    def resolve_providers(self, *, tenant_id: str, currency: str, operation: str | None = None, metadata: Mapping[str, object] | None = None, now=None) -> tuple[PaymentProviderContract, ...]:
        return tuple(self._registry.get(selection.provider_name).provider for selection in self.list_candidates(tenant_id=tenant_id, currency=currency, operation=operation, metadata=metadata, now=now))

    def mark_provider_success(self, provider_name: str) -> None:
        self._health.mark_success(provider_name)

    def mark_provider_failure(self, provider_name: str, *, reason: str, cooldown_seconds: int = 60, now=None) -> None:
        self._health.mark_failure(provider_name, reason=reason, cooldown_seconds=cooldown_seconds, now=now or utc_now())


PaymentProviderRouter.select = PaymentProviderRouter.route_payment_provider

__all__ = ['CANON_BILLING_PAYMENT_PROVIDER_ROUTER', 'PaymentProviderRouter', 'PaymentProviderSelection']

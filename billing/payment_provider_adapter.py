from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from billing.commercial_cycle_contract import CommercialCollectionAttempt, CommercialCollectionResult
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract
from billing.payment_provider_registry import PaymentProviderRegistry
from billing.payment_provider_router import PaymentProviderRouter


CANON_BILLING_PAYMENT_PROVIDER_ADAPTER = True


class RoutingPaymentProviderAdapter(PaymentProviderContract):
    """Thin routing adapter that preserves the provider contract while delegating
    provider choice to the canonical billing router.

    This keeps commercial routing outside of collection/refund orchestration and
    avoids hard-wiring a single provider into every billing execution path.
    """

    def __init__(self, *, router: PaymentProviderRouter, registry: PaymentProviderRegistry) -> None:
        self._router = router
        self._registry = registry

    def provider_name(self) -> str:
        return 'routed'

    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata: Mapping[str, object] | None = None) -> PaymentCustomerProfile:
        normalized_metadata = dict(metadata or {})
        currency = str(normalized_metadata.get('currency') or '').strip().upper()
        if not currency:
            raise ValueError('ensure_customer requires metadata.currency for routed provider selection')
        candidates = self._ordered_providers(tenant_id=tenant_id, currency=currency, operation='ensure_customer', metadata=normalized_metadata)
        last_error: Exception | None = None
        for provider in candidates:
            registration = self._registry.get(provider.provider_name())
            try:
                profile = provider.ensure_customer(tenant_id=tenant_id, email=email, metadata={**normalized_metadata, 'provider_backend_key': registration.backend_key})
                self._router.mark_provider_success(provider.provider_name())
                normalized = profile.normalized_copy()
                return replace(
                    normalized,
                    metadata={**dict(normalized.metadata), 'owner': 'billing.payment_provider_adapter', 'routed_provider': provider.provider_name(), 'provider_backend_key': registration.backend_key},
                )
            except Exception as exc:  # fail over to the next provider
                last_error = exc
                self._router.mark_provider_failure(provider.provider_name(), reason=f'ensure_customer:{type(exc).__name__}')
        if last_error is not None:
            raise RuntimeError('all routed providers failed ensure_customer') from last_error
        raise LookupError('no routed provider available for ensure_customer')

    def collect(self, attempt: CommercialCollectionAttempt) -> CommercialCollectionResult:
        attempt.validate()
        last_error: Exception | None = None
        for provider in self._ordered_providers(tenant_id=attempt.tenant_id, currency=attempt.currency, operation='collect', metadata=attempt.metadata, now=attempt.scheduled_at):
            registration = self._registry.get(provider.provider_name())
            delegated_attempt = replace(
                attempt,
                provider_name=provider.provider_name(),
                metadata={**dict(attempt.metadata), 'owner': 'billing.payment_provider_adapter', 'routed_provider': provider.provider_name(), 'provider_backend_key': registration.backend_key},
            )
            try:
                result = provider.collect(delegated_attempt)
                result.validate()
                if str(result.provider_name).strip().lower() != str(provider.provider_name()).strip().lower():
                    raise ValueError('routed provider returned mismatched provider_name')
                self._router.mark_provider_success(provider.provider_name())
                return replace(
                    result,
                    metadata={**dict(result.metadata), 'owner': 'billing.payment_provider_adapter', 'routed_provider': provider.provider_name(), 'provider_backend_key': registration.backend_key},
                )
            except Exception as exc:  # fail over to next provider
                last_error = exc
                self._router.mark_provider_failure(provider.provider_name(), reason=f'collect:{type(exc).__name__}', now=attempt.scheduled_at)
        if last_error is not None:
            raise RuntimeError('all routed providers failed collection') from last_error
        raise LookupError('no routed provider available for collection')

    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata: Mapping[str, object] | None = None) -> Mapping[str, object]:
        normalized_currency = str(currency or '').strip().upper()
        if not normalized_currency:
            raise ValueError('currency is required')
        normalized_metadata = dict(metadata or {})
        last_error: Exception | None = None
        strict_affinity = self._has_strict_affinity(normalized_metadata, operation='refund')
        providers = self._ordered_providers(tenant_id=tenant_id, currency=normalized_currency, operation='refund', metadata={**normalized_metadata, 'strict_provider_affinity': strict_affinity})
        if strict_affinity and providers:
            affinity = self._extract_preferred_provider(normalized_metadata)
            if affinity is not None and str(providers[0].provider_name()).strip().lower() != str(affinity).strip().lower():
                raise LookupError('preferred refund provider is not available')
        for provider in providers:
            registration = self._registry.get(provider.provider_name())
            try:
                payload = dict(
                    provider.refund(
                        invoice_id=invoice_id,
                        tenant_id=tenant_id,
                        amount_minor=int(amount_minor),
                        currency=normalized_currency,
                        reason=reason,
                        metadata={**normalized_metadata, 'owner': 'billing.payment_provider_adapter', 'routed_provider': provider.provider_name(), 'provider_backend_key': registration.backend_key},
                    )
                )
                payload.setdefault('provider_name', provider.provider_name())
                payload.setdefault('provider_backend_key', registration.backend_key)
                if str(payload.get('provider_name') or '').strip().lower() != str(provider.provider_name()).strip().lower():
                    raise ValueError('routed provider refund returned mismatched provider_name')
                self._router.mark_provider_success(provider.provider_name())
                return payload
            except Exception as exc:
                last_error = exc
                self._router.mark_provider_failure(provider.provider_name(), reason=f'refund:{type(exc).__name__}')
        if last_error is not None:
            raise RuntimeError('all routed providers failed refund') from last_error
        raise LookupError('no routed provider available for refund')

    def _ordered_providers(self, *, tenant_id: str, currency: str, operation: str, metadata: Mapping[str, object], now=None) -> tuple[PaymentProviderContract, ...]:
        candidates = list(self._router.resolve_providers(tenant_id=tenant_id, currency=currency, operation=operation, metadata=metadata, now=now))
        if not candidates:
            return ()
        preferred_provider = self._extract_preferred_provider(metadata)
        if preferred_provider is None:
            return tuple(candidates)
        preferred_key = preferred_provider.lower()
        prioritized = [provider for provider in candidates if str(provider.provider_name()).strip().lower() == preferred_key]
        fallback = [provider for provider in candidates if str(provider.provider_name()).strip().lower() != preferred_key]
        return tuple(prioritized + fallback)

    def _extract_preferred_provider(self, metadata: Mapping[str, object]) -> str | None:
        explicit = str(metadata.get('preferred_provider') or metadata.get('provider_name_hint') or '').strip()
        if explicit:
            try:
                self._registry.get(explicit)
            except LookupError:
                return None
            return explicit
        provider_customer_id = str(metadata.get('provider_customer_id') or '').strip()
        if ':' in provider_customer_id:
            candidate = provider_customer_id.split(':', 1)[0].strip()
            if candidate:
                try:
                    self._registry.get(candidate)
                except LookupError:
                    return None
                return candidate
        return None

    @staticmethod
    def _has_strict_affinity(metadata: Mapping[str, object], *, operation: str) -> bool:
        if str(operation).strip().lower() != 'refund':
            return False
        if 'strict_provider_affinity' in metadata:
            return bool(metadata.get('strict_provider_affinity'))
        if metadata.get('preferred_provider') or metadata.get('provider_name_hint'):
            return True
        provider_customer_id = str(metadata.get('provider_customer_id') or '').strip()
        return ':' in provider_customer_id


__all__ = ['CANON_BILLING_PAYMENT_PROVIDER_ADAPTER', 'RoutingPaymentProviderAdapter']

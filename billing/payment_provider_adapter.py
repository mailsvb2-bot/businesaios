from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from typing import Any

from billing.commercial_cycle_contract import (
    CommercialCollectionAttempt,
    CommercialCollectionResult,
    require_commercial_int,
)
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract
from billing.payment_provider_registry import PaymentProviderRegistry
from billing.payment_provider_router import PaymentProviderRouter
from core.tenancy.normalization import require_tenant_id

CANON_BILLING_PAYMENT_PROVIDER_ADAPTER = True


def _require_mapping(name: str, value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


class RoutingPaymentProviderAdapter(PaymentProviderContract):
    """Route a billing operation to one provider without post-call failover.

    Candidate selection may skip providers before an external call begins. Once a
    provider call starts, any exception is treated as an ambiguous outcome and is
    never retried against another provider, preventing duplicate charges/refunds.
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

    def ensure_customer(
        self,
        *,
        tenant_id: str,
        email: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> PaymentCustomerProfile:
        tenant = self._require_tenant(tenant_id)
        if email is not None and not isinstance(email, str):
            raise ValueError("email must be a string")
        normalized_metadata = self._metadata_copy(metadata)
        currency_value = normalized_metadata.get("currency")
        if not isinstance(currency_value, str) or not currency_value.strip():
            raise ValueError("ensure_customer requires metadata.currency for routed provider selection")
        currency = currency_value.strip().upper()
        provider = self._first_provider(
            tenant_id=tenant,
            currency=currency,
            operation="ensure_customer",
            metadata=normalized_metadata,
            missing_message="no routed provider available for ensure_customer",
        )
        provider_name, registration = self._registration_for(provider)
        try:
            profile = provider.ensure_customer(
                tenant_id=tenant,
                email=email,
                metadata={
                    **normalized_metadata,
                    "provider_backend_key": registration.backend_key,
                },
            )
        except Exception as exc:
            self._safe_mark_failure(provider_name, reason=f"ensure_customer:{type(exc).__name__}")
            raise RuntimeError("routed provider failed ensure_customer") from exc
        try:
            if not isinstance(profile, PaymentCustomerProfile):
                raise ValueError("routed provider must return PaymentCustomerProfile")
            normalized = profile.normalized_copy()
            if normalized.tenant_id != tenant:
                raise ValueError("routed provider returned mismatched tenant_id")
            if normalized.default_currency != currency:
                raise ValueError("routed provider returned mismatched default_currency")
        except Exception as exc:
            self._safe_mark_failure(provider_name, reason=f"ensure_customer_result:{type(exc).__name__}")
            raise RuntimeError("routed provider returned invalid customer profile") from exc
        self._safe_mark_success(provider_name)
        return replace(
            normalized,
            metadata={
                **deepcopy(dict(normalized.metadata)),
                "owner": "billing.payment_provider_adapter",
                "routed_provider": provider_name,
                "provider_backend_key": registration.backend_key,
            },
        )

    def collect(self, attempt: CommercialCollectionAttempt) -> CommercialCollectionResult:
        if not isinstance(attempt, CommercialCollectionAttempt):
            raise ValueError("attempt must be CommercialCollectionAttempt")
        attempt.validate()
        provider = self._first_provider(
            tenant_id=attempt.tenant_id,
            currency=attempt.currency,
            operation="collect",
            metadata=attempt.metadata,
            now=attempt.scheduled_at,
            missing_message="no routed provider available for collection",
        )
        provider_name, registration = self._registration_for(provider)
        delegated_attempt = replace(
            attempt,
            provider_name=provider_name,
            metadata={
                **deepcopy(dict(attempt.metadata)),
                "owner": "billing.payment_provider_adapter",
                "routed_provider": provider_name,
                "provider_backend_key": registration.backend_key,
            },
        )
        try:
            result = provider.collect(delegated_attempt)
        except Exception as exc:
            self._safe_mark_failure(
                provider_name,
                reason=f"collect:{type(exc).__name__}",
                now=attempt.scheduled_at,
            )
            raise RuntimeError("routed provider failed collection") from exc
        try:
            if not isinstance(result, CommercialCollectionResult):
                raise ValueError("routed provider must return CommercialCollectionResult")
            result.validate()
            if result.invoice_id != attempt.invoice_id:
                raise ValueError("routed provider returned mismatched invoice_id")
            if result.tenant_id != attempt.tenant_id:
                raise ValueError("routed provider returned mismatched tenant_id")
            if result.provider_name.strip().lower() != provider_name.lower():
                raise ValueError("routed provider returned mismatched provider_name")
        except Exception as exc:
            self._safe_mark_failure(
                provider_name,
                reason=f"collect_result:{type(exc).__name__}",
                now=attempt.scheduled_at,
            )
            raise RuntimeError("routed provider returned invalid collection result") from exc
        self._safe_mark_success(provider_name)
        return replace(
            result,
            metadata={
                **deepcopy(dict(result.metadata)),
                "owner": "billing.payment_provider_adapter",
                "routed_provider": provider_name,
                "provider_backend_key": registration.backend_key,
            },
        )

    def refund(
        self,
        *,
        invoice_id: str,
        tenant_id: str,
        amount_minor: int,
        currency: str,
        reason: str,
        metadata: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        if not isinstance(invoice_id, str) or not invoice_id.strip():
            raise ValueError("invoice_id is required")
        tenant = self._require_tenant(tenant_id)
        amount = require_commercial_int("amount_minor", amount_minor, minimum=1)
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("currency is required")
        normalized_currency = currency.strip().upper()
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason is required")
        normalized_metadata = self._metadata_copy(metadata)
        strict_affinity = self._has_strict_affinity(normalized_metadata, operation="refund")
        providers = self._ordered_providers(
            tenant_id=tenant,
            currency=normalized_currency,
            operation="refund",
            metadata={
                **normalized_metadata,
                "strict_provider_affinity": strict_affinity,
            },
        )
        if not providers:
            raise LookupError("no routed provider available for refund")
        provider = providers[0]
        provider_name, registration = self._registration_for(provider)
        if strict_affinity:
            affinity = self._extract_preferred_provider(normalized_metadata)
            if affinity is None or provider_name.lower() != affinity.lower():
                raise LookupError("preferred refund provider is not available")
        try:
            raw_payload = provider.refund(
                invoice_id=invoice_id.strip(),
                tenant_id=tenant,
                amount_minor=amount,
                currency=normalized_currency,
                reason=reason.strip(),
                metadata={
                    **normalized_metadata,
                    "owner": "billing.payment_provider_adapter",
                    "routed_provider": provider_name,
                    "provider_backend_key": registration.backend_key,
                },
            )
        except Exception as exc:
            self._safe_mark_failure(provider_name, reason=f"refund:{type(exc).__name__}")
            raise RuntimeError("routed provider failed refund") from exc
        try:
            payload = deepcopy(dict(_require_mapping("refund result", raw_payload)))
            payload.setdefault("provider_name", provider_name)
            payload.setdefault("provider_backend_key", registration.backend_key)
            self._assert_optional_binding(payload, "invoice_id", invoice_id.strip())
            self._assert_optional_binding(payload, "tenant_id", tenant)
            self._assert_optional_binding(payload, "currency", normalized_currency)
            if "amount_minor" in payload:
                returned_amount = require_commercial_int(
                    "refund result amount_minor", payload["amount_minor"], minimum=1
                )
                if returned_amount != amount:
                    raise ValueError("routed provider refund returned mismatched amount_minor")
            returned_provider = payload.get("provider_name")
            if not isinstance(returned_provider, str) or returned_provider.strip().lower() != provider_name.lower():
                raise ValueError("routed provider refund returned mismatched provider_name")
        except Exception as exc:
            self._safe_mark_failure(provider_name, reason=f"refund_result:{type(exc).__name__}")
            raise RuntimeError("routed provider returned invalid refund result") from exc
        self._safe_mark_success(provider_name)
        return payload

    def _first_provider(
        self,
        *,
        tenant_id: str,
        currency: str,
        operation: str,
        metadata: Mapping[str, object],
        missing_message: str,
        now: datetime | None = None,
    ) -> PaymentProviderContract:
        providers = self._ordered_providers(
            tenant_id=tenant_id,
            currency=currency,
            operation=operation,
            metadata=metadata,
            now=now,
        )
        if not providers:
            raise LookupError(missing_message)
        return providers[0]

    def _ordered_providers(
        self,
        *,
        tenant_id: str,
        currency: str,
        operation: str,
        metadata: Mapping[str, object],
        now: datetime | None = None,
    ) -> tuple[PaymentProviderContract, ...]:
        _require_mapping("metadata", metadata)
        candidates = list(
            self._router.resolve_providers(
                tenant_id=tenant_id,
                currency=currency,
                operation=operation,
                metadata=metadata,
                now=now,
            )
        )
        if not candidates:
            return ()
        preferred_provider = self._extract_preferred_provider(metadata)
        if preferred_provider is None:
            return tuple(candidates)
        preferred_key = preferred_provider.lower()
        prioritized = [
            provider
            for provider in candidates
            if self._provider_name(provider).lower() == preferred_key
        ]
        fallback = [
            provider
            for provider in candidates
            if self._provider_name(provider).lower() != preferred_key
        ]
        return tuple(prioritized + fallback)

    def _extract_preferred_provider(self, metadata: Mapping[str, object]) -> str | None:
        _require_mapping("metadata", metadata)
        explicit_value = metadata.get("preferred_provider") or metadata.get("provider_name_hint")
        if explicit_value is not None:
            if not isinstance(explicit_value, str):
                raise ValueError("preferred provider must be a string")
            explicit = explicit_value.strip()
            if explicit:
                self._registry.get(explicit)
                return explicit
        customer_value = metadata.get("provider_customer_id")
        if customer_value is not None and not isinstance(customer_value, str):
            raise ValueError("provider_customer_id must be a string")
        provider_customer_id = str(customer_value or "").strip()
        if ":" in provider_customer_id:
            candidate = provider_customer_id.split(":", 1)[0].strip()
            if candidate:
                self._registry.get(candidate)
                return candidate
        return None

    @staticmethod
    def _has_strict_affinity(metadata: Mapping[str, object], *, operation: str) -> bool:
        _require_mapping("metadata", metadata)
        if not isinstance(operation, str):
            raise ValueError("operation must be a string")
        if operation.strip().lower() != "refund":
            return False
        if "strict_provider_affinity" in metadata:
            value = metadata["strict_provider_affinity"]
            if not isinstance(value, bool):
                raise ValueError("strict_provider_affinity must be a boolean")
            return value
        for name in ("preferred_provider", "provider_name_hint"):
            value = metadata.get(name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} must be a string")
            if isinstance(value, str) and value.strip():
                return True
        customer_value = metadata.get("provider_customer_id")
        if customer_value is not None and not isinstance(customer_value, str):
            raise ValueError("provider_customer_id must be a string")
        return ":" in str(customer_value or "").strip()

    def _registration_for(self, provider: PaymentProviderContract):
        provider_name = self._provider_name(provider)
        return provider_name, self._registry.get(provider_name)

    @staticmethod
    def _provider_name(provider: PaymentProviderContract) -> str:
        provider_name_fn = getattr(provider, "provider_name", None)
        if not callable(provider_name_fn):
            raise ValueError("provider must expose provider_name()")
        value = provider_name_fn()
        if not isinstance(value, str) or not value.strip():
            raise ValueError("provider.provider_name() must return a non-empty string")
        return value.strip()

    @staticmethod
    def _metadata_copy(metadata: Mapping[str, object] | None) -> dict[str, object]:
        if metadata is None:
            return {}
        return deepcopy(dict(_require_mapping("metadata", metadata)))

    @staticmethod
    def _require_tenant(tenant_id: str) -> str:
        if not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a string")
        return require_tenant_id(tenant_id)

    @staticmethod
    def _assert_optional_binding(payload: Mapping[str, object], name: str, expected: str) -> None:
        if name not in payload:
            return
        value = payload[name]
        if not isinstance(value, str) or value.strip().upper() != expected.strip().upper():
            raise ValueError(f"routed provider refund returned mismatched {name}")

    def _safe_mark_success(self, provider_name: str) -> None:
        try:
            self._router.mark_provider_success(provider_name)
        except Exception:
            return

    def _safe_mark_failure(
        self,
        provider_name: str,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> None:
        try:
            self._router.mark_provider_failure(provider_name, reason=reason, now=now)
        except Exception:
            return


__all__ = ["CANON_BILLING_PAYMENT_PROVIDER_ADAPTER", "RoutingPaymentProviderAdapter"]

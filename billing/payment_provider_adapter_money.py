from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace

from billing.commercial_cycle_contract import (
    CommercialCollectionAttempt,
    CommercialCollectionResult,
    require_commercial_int,
)
from billing.payment_provider_adapter_helpers import require_mapping
from billing.payment_provider_contract import PaymentCheckoutRequest, PaymentCheckoutSession


class PaymentProviderMoneyMixin:
    def create_checkout(self, request: PaymentCheckoutRequest) -> PaymentCheckoutSession:
        if not isinstance(request, PaymentCheckoutRequest):
            raise ValueError("request must be PaymentCheckoutRequest")
        normalized = request.normalized_copy()
        provider = self._first_provider(tenant_id=normalized.tenant_id, currency=normalized.currency, operation="checkout", metadata=normalized.metadata, missing_message="no routed provider available for checkout")
        provider_name, registration = self._registration_for(provider)
        routing = {"owner": "billing.payment_provider_adapter", "routed_provider": provider_name, "provider_backend_key": registration.backend_key}
        delegated = replace(normalized, metadata={**deepcopy(dict(normalized.metadata)), **routing})
        try:
            result = provider.create_checkout(delegated)
            if not isinstance(result, PaymentCheckoutSession):
                raise ValueError("routed provider must return PaymentCheckoutSession")
            result = result.normalized_copy()
            if result.tenant_id != normalized.tenant_id or result.provider_name.lower() != provider_name.lower():
                raise ValueError("routed checkout returned mismatched tenant/provider binding")
            if result.amount_minor != normalized.amount_minor or result.currency != normalized.currency:
                raise ValueError("routed checkout returned mismatched amount or currency")
        except Exception as exc:
            self._safe_mark_failure(provider_name, reason=f"checkout:{type(exc).__name__}")
            raise RuntimeError("routed provider failed checkout") from exc
        self._safe_mark_success(provider_name)
        return replace(result, metadata={**deepcopy(dict(result.metadata)), **routing})

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
            payload = deepcopy(dict(require_mapping("refund result", raw_payload)))
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


__all__ = ["PaymentProviderMoneyMixin"]

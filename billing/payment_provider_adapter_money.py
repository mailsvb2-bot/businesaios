from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace

from billing.commercial_cycle_contract import CommercialCollectionAttempt, CommercialCollectionResult, require_commercial_int
from billing.payment_provider_adapter_helpers import require_mapping
from billing.payment_provider_contract import PaymentCheckoutRequest, PaymentCheckoutSession


class PaymentProviderMoneyMixin:
    @staticmethod
    def _routing_metadata(provider_name: str, backend_key: str) -> dict[str, str]:
        return {"owner": "billing.payment_provider_adapter", "routed_provider": provider_name, "provider_backend_key": backend_key}

    def create_checkout(self, request: PaymentCheckoutRequest) -> PaymentCheckoutSession:
        if not isinstance(request, PaymentCheckoutRequest):
            raise ValueError("request must be PaymentCheckoutRequest")
        normalized = request.normalized_copy()
        provider = self._first_provider(tenant_id=normalized.tenant_id, currency=normalized.currency, operation="checkout", metadata=normalized.metadata, missing_message="no routed provider available for checkout")
        provider_name, registration = self._registration_for(provider)
        routing = self._routing_metadata(provider_name, registration.backend_key)
        try:
            result = provider.create_checkout(replace(normalized, metadata={**deepcopy(dict(normalized.metadata)), **routing}))
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

    def get_payment_status(self, *, tenant_id: str, currency: str, provider_name: str, external_reference: str) -> str:
        tenant, normalized_currency = self._require_tenant(tenant_id), str(currency or "").strip().upper()
        affinity, external_id = str(provider_name or "").strip(), str(external_reference or "").strip()
        if not normalized_currency or not affinity or not external_id:
            raise ValueError("currency, provider_name and external_reference are required")
        provider = self._first_provider(tenant_id=tenant, currency=normalized_currency, operation="status", metadata={"provider_name_hint": affinity}, missing_message="recorded payment provider is unavailable for status")
        routed_name, _ = self._registration_for(provider)
        if routed_name.lower() != affinity.lower():
            raise LookupError("recorded payment provider affinity mismatch")
        try:
            status = str(provider.get_payment_status(tenant_id=tenant, currency=normalized_currency, provider_name=routed_name, external_reference=external_id) or "").strip().lower()
            if not status:
                raise ValueError("routed provider returned empty payment status")
        except Exception as exc:
            self._safe_mark_failure(routed_name, reason=f"status:{type(exc).__name__}")
            raise RuntimeError("routed provider failed payment status read") from exc
        self._safe_mark_success(routed_name)
        return status

    def collect(self, attempt: CommercialCollectionAttempt) -> CommercialCollectionResult:
        if not isinstance(attempt, CommercialCollectionAttempt):
            raise ValueError("attempt must be CommercialCollectionAttempt")
        attempt.validate()
        provider = self._first_provider(tenant_id=attempt.tenant_id, currency=attempt.currency, operation="collect", metadata=attempt.metadata, now=attempt.scheduled_at, missing_message="no routed provider available for collection")
        provider_name, registration = self._registration_for(provider)
        routing = self._routing_metadata(provider_name, registration.backend_key)
        delegated = replace(attempt, provider_name=provider_name, metadata={**deepcopy(dict(attempt.metadata)), **routing})
        try:
            result = provider.collect(delegated)
        except Exception as exc:
            self._safe_mark_failure(provider_name, reason=f"collect:{type(exc).__name__}", now=attempt.scheduled_at)
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
            self._safe_mark_failure(provider_name, reason=f"collect_result:{type(exc).__name__}", now=attempt.scheduled_at)
            raise RuntimeError("routed provider returned invalid collection result") from exc
        self._safe_mark_success(provider_name)
        return replace(result, metadata={**deepcopy(dict(result.metadata)), **routing})

    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata: Mapping[str, object] | None = None) -> Mapping[str, object]:
        if not isinstance(invoice_id, str) or not invoice_id.strip():
            raise ValueError("invoice_id is required")
        tenant, amount = self._require_tenant(tenant_id), require_commercial_int("amount_minor", amount_minor, minimum=1)
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("currency is required")
        normalized_currency = currency.strip().upper()
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason is required")
        normalized_metadata = self._metadata_copy(metadata)
        strict_affinity = self._has_strict_affinity(normalized_metadata, operation="refund")
        providers = self._ordered_providers(tenant_id=tenant, currency=normalized_currency, operation="refund", metadata={**normalized_metadata, "strict_provider_affinity": strict_affinity})
        if not providers:
            raise LookupError("no routed provider available for refund")
        provider = providers[0]
        provider_name, registration = self._registration_for(provider)
        if strict_affinity:
            affinity = self._extract_preferred_provider(normalized_metadata)
            if affinity is None or provider_name.lower() != affinity.lower():
                raise LookupError("preferred refund provider is not available")
        routing = self._routing_metadata(provider_name, registration.backend_key)
        try:
            raw = provider.refund(invoice_id=invoice_id.strip(), tenant_id=tenant, amount_minor=amount, currency=normalized_currency, reason=reason.strip(), metadata={**normalized_metadata, **routing})
        except Exception as exc:
            self._safe_mark_failure(provider_name, reason=f"refund:{type(exc).__name__}")
            raise RuntimeError("routed provider failed refund") from exc
        try:
            payload = deepcopy(dict(require_mapping("refund result", raw)))
            payload.setdefault("provider_name", provider_name)
            payload.setdefault("provider_backend_key", registration.backend_key)
            for name, expected in (("invoice_id", invoice_id.strip()), ("tenant_id", tenant), ("currency", normalized_currency)):
                self._assert_optional_binding(payload, name, expected)
            if "amount_minor" in payload and require_commercial_int("refund result amount_minor", payload["amount_minor"], minimum=1) != amount:
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
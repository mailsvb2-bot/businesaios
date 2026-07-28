from __future__ import annotations

import hashlib
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace

from billing.payment_provider_contract import PaymentCustomerProfile


class PaymentProviderCustomerMixin:
    def ensure_customer(
        self,
        *,
        tenant_id: str,
        email: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> PaymentCustomerProfile:
        """Provision through one preselected healthy provider.

        Routing may skip a provider that was already known to be unavailable before
        dispatch. Once ``ensure_customer`` starts, any exception or invalid response
        is an ambiguous external outcome and must not be sent to a second provider.
        A deterministic key is still supplied for safe operator reconciliation and
        retry against the same provider.
        """

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
        provisioning_key = self._customer_provisioning_key(
            tenant_id=tenant,
            email=email,
            currency=currency,
        )
        try:
            profile = provider.ensure_customer(
                tenant_id=tenant,
                email=email,
                metadata={
                    **normalized_metadata,
                    "provider_backend_key": registration.backend_key,
                    "customer_provisioning_idempotency_key": provisioning_key,
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
                "customer_provisioning_idempotency_key": provisioning_key,
            },
        )

    @staticmethod
    def _customer_provisioning_key(*, tenant_id: str, email: str | None, currency: str) -> str:
        material = "|".join(
            (
                str(tenant_id).strip(),
                str(email or "").strip().lower(),
                str(currency).strip().upper(),
            )
        )
        return "customer-provisioning:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


__all__ = ["PaymentProviderCustomerMixin"]

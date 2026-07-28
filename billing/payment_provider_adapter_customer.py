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
        """Provision a customer with deterministic, safe provider failover.

        Customer provisioning is not a money movement. Every candidate receives
        the same stable provisioning idempotency key, so a provider exception can
        be followed by the next healthy candidate. Monetary operations remain
        single-attempt after dispatch.
        """

        tenant = self._require_tenant(tenant_id)
        if email is not None and not isinstance(email, str):
            raise ValueError("email must be a string")
        normalized_metadata = self._metadata_copy(metadata)
        currency_value = normalized_metadata.get("currency")
        if not isinstance(currency_value, str) or not currency_value.strip():
            raise ValueError("ensure_customer requires metadata.currency for routed provider selection")
        currency = currency_value.strip().upper()
        providers = self._ordered_providers(
            tenant_id=tenant,
            currency=currency,
            operation="ensure_customer",
            metadata=normalized_metadata,
        )
        if not providers:
            raise LookupError("no routed provider available for ensure_customer")
        provisioning_key = self._customer_provisioning_key(
            tenant_id=tenant,
            email=email,
            currency=currency,
        )
        last_error: Exception | None = None
        for provider in providers:
            provider_name, registration = self._registration_for(provider)
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
                if not isinstance(profile, PaymentCustomerProfile):
                    raise ValueError("routed provider must return PaymentCustomerProfile")
                normalized = profile.normalized_copy()
                if normalized.tenant_id != tenant:
                    raise ValueError("routed provider returned mismatched tenant_id")
                if normalized.default_currency != currency:
                    raise ValueError("routed provider returned mismatched default_currency")
            except Exception as exc:
                last_error = exc
                self._safe_mark_failure(provider_name, reason=f"ensure_customer:{type(exc).__name__}")
                continue
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
        raise RuntimeError("all routed providers failed ensure_customer") from last_error

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

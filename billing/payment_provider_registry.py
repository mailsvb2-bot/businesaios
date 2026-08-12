from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from threading import RLock
from typing import Any

from billing.commercial_cycle_contract import require_commercial_int
from billing.payment_provider_capability import PaymentProviderCapabilities
from billing.payment_provider_contract import PaymentProviderContract

CANON_BILLING_PAYMENT_PROVIDER_REGISTRY = True
_PROVIDER_METHODS = {"ensure_customer": "ensure_customer", "checkout": "create_checkout", "collect": "collect", "refund": "refund"}


def _normalize_string_tuple(name: str, values: Any, *, transform) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, Mapping)) or not isinstance(values, Iterable):
        raise ValueError(f"{name} must be an iterable of strings")
    values = tuple(values)
    if any(not isinstance(item, str) for item in values):
        raise ValueError(f"{name} must contain strings")
    normalized = tuple(transform(item.strip()) for item in values)
    if any(not item for item in normalized):
        raise ValueError(f"{name} cannot contain blank values")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must be unique")
    return tuple(sorted(normalized))


@dataclass(frozen=True)
class PaymentProviderRegistration:
    provider_name: str
    provider: PaymentProviderContract
    currencies: tuple[str, ...] = ()
    priority: int = 100
    tenant_allowlist: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    capabilities: PaymentProviderCapabilities = field(default_factory=PaymentProviderCapabilities)
    backend_key: str = "generic"

    def validate(self) -> None:
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise ValueError("provider_name is required")
        provider_name_fn = getattr(self.provider, "provider_name", None)
        if not callable(provider_name_fn):
            raise ValueError("provider must expose provider_name()")
        reported = provider_name_fn()
        if not isinstance(reported, str) or not reported.strip():
            raise ValueError("provider.provider_name() must return a non-empty string")
        if reported.strip().lower() != self.provider_name.strip().lower():
            raise ValueError("provider_name must match provider.provider_name()")
        require_commercial_int("priority", self.priority, minimum=0)
        _normalize_string_tuple("currencies", self.currencies, transform=str.upper)
        _normalize_string_tuple("tenant_allowlist", self.tenant_allowlist, transform=lambda value: value)
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        if not isinstance(self.capabilities, PaymentProviderCapabilities):
            raise ValueError("capabilities must be PaymentProviderCapabilities")
        self.capabilities.validate()
        for operation in self.capabilities.operations:
            if not callable(getattr(self.provider, _PROVIDER_METHODS[operation.strip().lower()], None)):
                raise ValueError(f"provider does not implement advertised operation: {operation}")
        if not isinstance(self.backend_key, str) or not self.backend_key.strip():
            raise ValueError("backend_key is required")

    def normalized_copy(self) -> PaymentProviderRegistration:
        self.validate()
        return replace(self, provider_name=self.provider_name.strip(), currencies=_normalize_string_tuple("currencies", self.currencies, transform=str.upper), tenant_allowlist=_normalize_string_tuple("tenant_allowlist", self.tenant_allowlist, transform=lambda value: value), metadata=deepcopy(dict(self.metadata)), capabilities=self.capabilities.normalized_copy(), backend_key=self.backend_key.strip().lower())

    def supports_operation(self, *, operation: str, metadata: Mapping[str, object] | None = None) -> bool:
        normalized = self.normalized_copy()
        if not isinstance(operation, str):
            raise ValueError("operation must be a string")
        operation = operation.strip().lower()
        if not operation:
            raise ValueError("operation is required")
        if not normalized.capabilities.supports(operation):
            return False
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        if operation != "refund":
            return True
        md = dict(metadata or {})
        if "strict_provider_affinity" in md and not isinstance(md["strict_provider_affinity"], bool):
            raise ValueError("strict_provider_affinity must be a boolean")
        if not (bool(md.get("strict_provider_affinity", False)) or normalized.capabilities.strict_affinity_for_refund):
            return True
        preferred = md.get("preferred_provider") or md.get("provider_name_hint")
        if preferred is not None and not isinstance(preferred, str):
            raise ValueError("preferred provider affinity must be a string")
        provider_customer_id = md.get("provider_customer_id")
        if provider_customer_id is not None and not isinstance(provider_customer_id, str):
            raise ValueError("provider_customer_id must be a string")
        customer_id = str(provider_customer_id or "").strip()
        affinity = str(preferred or "").strip() or (customer_id.split(":", 1)[0].strip() if ":" in customer_id else "")
        return bool(affinity) and affinity.lower() == normalized.provider_name.lower()

    def supports(self, *, tenant_id: str, currency: str) -> bool:
        normalized = self.normalized_copy()
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("currency is required")
        tenant, currency = tenant_id.strip(), currency.strip().upper()
        return (not normalized.tenant_allowlist or tenant in normalized.tenant_allowlist) and (not normalized.currencies or currency in normalized.currencies)


class PaymentProviderRegistry:
    def __init__(self, registrations: Iterable[PaymentProviderRegistration] | None = None) -> None:
        self._lock, self._registrations = RLock(), {}
        if registrations is not None and (isinstance(registrations, (str, bytes, Mapping)) or not isinstance(registrations, Iterable)):
            raise ValueError("registrations must be an iterable of registrations")
        for registration in registrations or ():
            self.register(registration)

    def register(self, registration: PaymentProviderRegistration) -> PaymentProviderRegistration:
        if not isinstance(registration, PaymentProviderRegistration):
            raise ValueError("registration must be PaymentProviderRegistration")
        normalized = registration.normalized_copy()
        with self._lock:
            existing = self._registrations.get(normalized.provider_name.lower())
            if existing is not None and existing != normalized:
                raise ValueError(f"provider {normalized.provider_name} already registered with different configuration")
            self._registrations[normalized.provider_name.lower()] = normalized
            return normalized.normalized_copy()

    def get(self, provider_name: str) -> PaymentProviderRegistration:
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name is required")
        with self._lock:
            try:
                return self._registrations[provider_name.strip().lower()].normalized_copy()
            except KeyError as exc:
                raise LookupError(f"unknown provider: {provider_name}") from exc

    def list_registrations(self) -> tuple[PaymentProviderRegistration, ...]:
        with self._lock:
            registrations = tuple(item.normalized_copy() for item in self._registrations.values())
        return tuple(sorted(registrations, key=lambda item: (item.priority, item.provider_name.lower())))


__all__ = ["CANON_BILLING_PAYMENT_PROVIDER_REGISTRY", "PaymentProviderRegistration", "PaymentProviderRegistry"]

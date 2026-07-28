from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from typing import Any

from billing.payment_provider_contract import PaymentProviderContract
from core.tenancy.normalization import require_tenant_id


def require_mapping(name: str, value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


class PaymentProviderRoutingMixin:
    _router: Any
    _registry: Any

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
        require_mapping("metadata", metadata)
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
        require_mapping("metadata", metadata)
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
        require_mapping("metadata", metadata)
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
        return deepcopy(dict(require_mapping("metadata", metadata)))

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


__all__ = ["PaymentProviderRoutingMixin", "require_mapping"]

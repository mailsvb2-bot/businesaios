from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from billing.commercial_cycle_contract import require_aware_datetime, utc_now
from billing.payment_provider_contract import PaymentProviderContract
from billing.payment_provider_health_registry import PaymentProviderHealthRegistry
from billing.payment_provider_registry import PaymentProviderRegistry
from core.tenancy.normalization import require_tenant_id

CANON_BILLING_PAYMENT_PROVIDER_ROUTER = True


@dataclass(frozen=True)
class PaymentProviderSelection:
    tenant_id: str
    currency: str
    provider_name: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.tenant_id, str):
            raise ValueError("tenant_id must be a string")
        require_tenant_id(self.tenant_id)
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise ValueError("currency is required")
        if self.currency != self.currency.strip().upper():
            raise ValueError("currency must use canonical uppercase form")
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise ValueError("provider_name is required")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")


class PaymentProviderRouter:
    def __init__(
        self,
        *,
        registry: PaymentProviderRegistry,
        health_registry: PaymentProviderHealthRegistry | None = None,
    ) -> None:
        if not isinstance(registry, PaymentProviderRegistry):
            raise ValueError("registry must be PaymentProviderRegistry")
        if health_registry is not None and not isinstance(
            health_registry, PaymentProviderHealthRegistry
        ):
            raise ValueError("health_registry must be PaymentProviderHealthRegistry")
        self._registry = registry
        self._health = (
            PaymentProviderHealthRegistry() if health_registry is None else health_registry
        )

    def list_candidates(
        self,
        *,
        tenant_id: str,
        currency: str,
        operation: str | None = None,
        metadata: Mapping[str, object] | None = None,
        now: datetime | None = None,
    ) -> tuple[PaymentProviderSelection, ...]:
        if not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a string")
        tenant = require_tenant_id(tenant_id)
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("currency is required")
        normalized_currency = currency.strip().upper()
        observed_at = utc_now() if now is None else require_aware_datetime("now", now)
        if operation is not None and not isinstance(operation, str):
            raise ValueError("operation must be a string")
        normalized_operation = None if operation is None else operation.strip().lower()
        if normalized_operation == "":
            raise ValueError("operation is required")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        candidate_metadata = dict(metadata or {})
        candidates: list[tuple[int, int, str, str, Any, Any]] = []
        for registration in self._registry.list_registrations():
            if not registration.supports(tenant_id=tenant, currency=normalized_currency):
                continue
            if normalized_operation is not None and not registration.supports_operation(
                operation=normalized_operation,
                metadata=candidate_metadata,
            ):
                continue
            if not self._health.is_available(registration.provider_name, now=observed_at):
                continue
            health = self._health.get(registration.provider_name)
            cooldown_sort = (
                "" if health.cooldown_until is None else health.cooldown_until.isoformat()
            )
            candidates.append(
                (
                    registration.priority,
                    health.failure_count,
                    cooldown_sort,
                    registration.provider_name.lower(),
                    registration,
                    health,
                )
            )
        ordered: list[PaymentProviderSelection] = []
        for _, failure_count, _, _, selected, health in sorted(candidates):
            result = PaymentProviderSelection(
                tenant_id=tenant,
                currency=normalized_currency,
                provider_name=selected.provider_name,
                metadata={
                    "owner": "billing.payment_provider_router",
                    "priority": selected.priority,
                    "failure_count": failure_count,
                    "cooldown_until": (
                        None
                        if health.cooldown_until is None
                        else health.cooldown_until.isoformat()
                    ),
                    "operation": normalized_operation,
                    "backend_key": selected.backend_key,
                },
            )
            result.validate()
            ordered.append(result)
        return tuple(ordered)

    def route_payment_provider(
        self,
        *,
        tenant_id: str,
        currency: str,
        operation: str | None = None,
        metadata: Mapping[str, object] | None = None,
        now: datetime | None = None,
    ) -> PaymentProviderSelection:
        candidates = self.list_candidates(
            tenant_id=tenant_id,
            currency=currency,
            operation=operation,
            metadata=metadata,
            now=now,
        )
        if not candidates:
            tenant = require_tenant_id(tenant_id)
            normalized_currency = currency.strip().upper()
            raise LookupError(
                f"no payment provider available for tenant={tenant} currency={normalized_currency}"
            )
        return candidates[0]

    def resolve_provider(
        self,
        *,
        tenant_id: str,
        currency: str,
        operation: str | None = None,
        metadata: Mapping[str, object] | None = None,
        now: datetime | None = None,
    ) -> PaymentProviderContract:
        selection = self.route_payment_provider(
            tenant_id=tenant_id,
            currency=currency,
            operation=operation,
            metadata=metadata,
            now=now,
        )
        return self._registry.get(selection.provider_name).provider

    def resolve_providers(
        self,
        *,
        tenant_id: str,
        currency: str,
        operation: str | None = None,
        metadata: Mapping[str, object] | None = None,
        now: datetime | None = None,
    ) -> tuple[PaymentProviderContract, ...]:
        return tuple(
            self._registry.get(selection.provider_name).provider
            for selection in self.list_candidates(
                tenant_id=tenant_id,
                currency=currency,
                operation=operation,
                metadata=metadata,
                now=now,
            )
        )

    def mark_provider_success(self, provider_name: str) -> None:
        self._health.mark_success(provider_name)

    def mark_provider_failure(
        self,
        provider_name: str,
        *,
        reason: str,
        cooldown_seconds: int = 60,
        now: datetime | None = None,
    ) -> None:
        self._health.mark_failure(
            provider_name,
            reason=reason,
            cooldown_seconds=cooldown_seconds,
            now=utc_now() if now is None else now,
        )


PaymentProviderRouter.select = PaymentProviderRouter.route_payment_provider

__all__ = [
    "CANON_BILLING_PAYMENT_PROVIDER_ROUTER",
    "PaymentProviderRouter",
    "PaymentProviderSelection",
]

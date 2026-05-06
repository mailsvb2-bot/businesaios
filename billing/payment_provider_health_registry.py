from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping

from billing.commercial_cycle_contract import utc_now


CANON_BILLING_PAYMENT_PROVIDER_HEALTH_REGISTRY = True


@dataclass(frozen=True)
class ProviderHealthStatus:
    provider_name: str
    healthy: bool = True
    cooldown_until: datetime | None = None
    failure_count: int = 0
    last_failure_reason: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.provider_name or '').strip():
            raise ValueError('provider_name is required')
        if self.cooldown_until is not None and self.cooldown_until.tzinfo is None:
            raise ValueError('cooldown_until must be timezone-aware')
        if int(self.failure_count) < 0:
            raise ValueError('failure_count must be >= 0')
        if self.healthy and self.last_failure_reason is not None and str(self.last_failure_reason).strip() and self.cooldown_until is None:
            raise ValueError('healthy provider cannot have last_failure_reason without cooldown')


class PaymentProviderHealthRegistry:
    def __init__(self) -> None:
        self._statuses: dict[str, ProviderHealthStatus] = {}

    def _normalize_key(self, provider_name: str) -> str:
        key = str(provider_name or '').strip().lower()
        if not key:
            raise ValueError('provider_name is required')
        return key

    def get(self, provider_name: str) -> ProviderHealthStatus:
        key = self._normalize_key(provider_name)
        status = self._statuses.get(key)
        if status is None:
            return ProviderHealthStatus(provider_name=key)
        status.validate()
        return status

    def mark_success(self, provider_name: str) -> ProviderHealthStatus:
        key = self._normalize_key(provider_name)
        status = ProviderHealthStatus(provider_name=key, healthy=True, failure_count=0, metadata={'owner': 'billing.payment_provider_health_registry'})
        self._statuses[key] = status
        return status

    def mark_failure(self, provider_name: str, *, reason: str, cooldown_seconds: int = 60, now: datetime | None = None) -> ProviderHealthStatus:
        key = self._normalize_key(provider_name)
        if not str(reason or '').strip():
            raise ValueError('reason is required')
        cooldown = int(cooldown_seconds)
        if cooldown < 0:
            raise ValueError('cooldown_seconds must be >= 0')
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        prior = self._statuses.get(key)
        failure_count = 1 if prior is None else int(prior.failure_count) + 1
        cooldown_until = observed_at + timedelta(seconds=cooldown)
        status = ProviderHealthStatus(
            provider_name=key,
            healthy=False,
            cooldown_until=cooldown_until,
            failure_count=failure_count,
            last_failure_reason=str(reason).strip(),
            metadata={'owner': 'billing.payment_provider_health_registry'},
        )
        self._statuses[key] = status
        return status

    def is_available(self, provider_name: str, *, now: datetime | None = None) -> bool:
        status = self.get(provider_name)
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        if status.cooldown_until is None:
            return bool(status.healthy)
        if observed_at < status.cooldown_until:
            return False
        return True


__all__ = ['CANON_BILLING_PAYMENT_PROVIDER_HEALTH_REGISTRY', 'PaymentProviderHealthRegistry', 'ProviderHealthStatus']

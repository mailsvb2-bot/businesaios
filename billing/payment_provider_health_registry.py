from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from threading import RLock
from typing import Any

from billing.commercial_cycle_contract import (
    require_aware_datetime,
    require_commercial_int,
    utc_now,
)

CANON_BILLING_PAYMENT_PROVIDER_HEALTH_REGISTRY = True


def _require_mapping(name: str, value: Any) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


@dataclass(frozen=True)
class ProviderHealthStatus:
    provider_name: str
    healthy: bool = True
    cooldown_until: datetime | None = None
    failure_count: int = 0
    last_failure_reason: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise ValueError("provider_name is required")
        if not isinstance(self.healthy, bool):
            raise ValueError("healthy must be a boolean")
        if self.cooldown_until is not None:
            require_aware_datetime("cooldown_until", self.cooldown_until)
        require_commercial_int("failure_count", self.failure_count, minimum=0)
        if self.last_failure_reason is not None and (
            not isinstance(self.last_failure_reason, str) or not self.last_failure_reason.strip()
        ):
            raise ValueError("last_failure_reason must be a non-empty string")
        _require_mapping("metadata", self.metadata)
        if self.healthy:
            if self.failure_count != 0:
                raise ValueError("healthy provider must have failure_count=0")
            if self.cooldown_until is not None or self.last_failure_reason is not None:
                raise ValueError("healthy provider cannot carry failure cooldown state")
        else:
            if self.failure_count <= 0:
                raise ValueError("unhealthy provider must have failure_count > 0")
            if self.cooldown_until is None:
                raise ValueError("unhealthy provider requires cooldown_until")
            if self.last_failure_reason is None:
                raise ValueError("unhealthy provider requires last_failure_reason")

    def normalized_copy(self) -> ProviderHealthStatus:
        self.validate()
        return replace(
            self,
            provider_name=self.provider_name.strip().lower(),
            last_failure_reason=(
                None if self.last_failure_reason is None else self.last_failure_reason.strip()
            ),
            metadata=deepcopy(dict(self.metadata)),
        )


class PaymentProviderHealthRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._statuses: dict[str, ProviderHealthStatus] = {}

    @staticmethod
    def _normalize_key(provider_name: str) -> str:
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name is required")
        return provider_name.strip().lower()

    def get(self, provider_name: str) -> ProviderHealthStatus:
        key = self._normalize_key(provider_name)
        with self._lock:
            status = self._statuses.get(key)
            if status is None:
                return ProviderHealthStatus(provider_name=key)
            return status.normalized_copy()

    def mark_success(self, provider_name: str) -> ProviderHealthStatus:
        key = self._normalize_key(provider_name)
        status = ProviderHealthStatus(
            provider_name=key,
            healthy=True,
            failure_count=0,
            metadata={"owner": "billing.payment_provider_health_registry"},
        )
        status.validate()
        with self._lock:
            self._statuses[key] = status
        return status.normalized_copy()

    def mark_failure(
        self,
        provider_name: str,
        *,
        reason: str,
        cooldown_seconds: int = 60,
        now: datetime | None = None,
    ) -> ProviderHealthStatus:
        key = self._normalize_key(provider_name)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason is required")
        cooldown = require_commercial_int("cooldown_seconds", cooldown_seconds, minimum=0)
        observed_at = utc_now() if now is None else require_aware_datetime("now", now)
        with self._lock:
            prior = self._statuses.get(key)
            failure_count = 1 if prior is None else prior.failure_count + 1
            status = ProviderHealthStatus(
                provider_name=key,
                healthy=False,
                cooldown_until=observed_at + timedelta(seconds=cooldown),
                failure_count=failure_count,
                last_failure_reason=reason.strip(),
                metadata={"owner": "billing.payment_provider_health_registry"},
            )
            status.validate()
            self._statuses[key] = status
        return status.normalized_copy()

    def is_available(self, provider_name: str, *, now: datetime | None = None) -> bool:
        status = self.get(provider_name)
        observed_at = utc_now() if now is None else require_aware_datetime("now", now)
        if status.cooldown_until is None:
            return status.healthy
        return observed_at >= status.cooldown_until


__all__ = [
    "CANON_BILLING_PAYMENT_PROVIDER_HEALTH_REGISTRY",
    "PaymentProviderHealthRegistry",
    "ProviderHealthStatus",
]

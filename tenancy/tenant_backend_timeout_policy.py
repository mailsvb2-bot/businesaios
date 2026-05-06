from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from tenancy.tenant_backend_clock_policy import ensure_aware, utc_now


CANON_TENANT_BACKEND_TIMEOUT_POLICY = True


@dataclass(frozen=True)
class TenantBackendTimeoutPolicy:
    acquire_timeout_seconds: float = 5.0
    renew_timeout_seconds: float = 5.0
    release_timeout_seconds: float = 5.0
    list_timeout_seconds: float = 10.0
    heartbeat_timeout_seconds: float = 5.0
    reconcile_timeout_seconds: float = 30.0
    selfcheck_timeout_seconds: float = 20.0

    def validate(self) -> None:
        for name in (
            'acquire_timeout_seconds',
            'renew_timeout_seconds',
            'release_timeout_seconds',
            'list_timeout_seconds',
            'heartbeat_timeout_seconds',
            'reconcile_timeout_seconds',
            'selfcheck_timeout_seconds',
        ):
            value = float(getattr(self, name))
            if value <= 0:
                raise ValueError(f'{name} must be > 0')

    def deadline(self, *, operation: str, now: datetime | None = None) -> datetime:
        self.validate()
        seconds = self._seconds_for(operation)
        return ensure_aware(now or utc_now()) + timedelta(seconds=seconds)

    def remaining_seconds(self, *, operation: str, deadline: datetime, now: datetime | None = None) -> float:
        self.validate()
        planned = ensure_aware(deadline)
        moment = ensure_aware(now or utc_now())
        self._seconds_for(operation)
        return max(0.0, float((planned - moment).total_seconds()))

    def assert_not_expired(self, *, operation: str, deadline: datetime, now: datetime | None = None) -> None:
        remaining = self.remaining_seconds(operation=operation, deadline=deadline, now=now)
        if remaining <= 0.0:
            raise TimeoutError(f'tenant backend timeout expired for operation={operation}')

    def _seconds_for(self, operation: str) -> float:
        name = str(operation or '').strip().lower()
        if not name:
            raise ValueError('operation is required')
        mapping = {
            'acquire': self.acquire_timeout_seconds,
            'renew': self.renew_timeout_seconds,
            'release': self.release_timeout_seconds,
            'list': self.list_timeout_seconds,
            'heartbeat': self.heartbeat_timeout_seconds,
            'reconcile': self.reconcile_timeout_seconds,
            'selfcheck': self.selfcheck_timeout_seconds,
        }
        if name not in mapping:
            raise KeyError(f'unsupported backend timeout operation: {name}')
        return float(mapping[name])


__all__ = ['CANON_TENANT_BACKEND_TIMEOUT_POLICY', 'TenantBackendTimeoutPolicy']

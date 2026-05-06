from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol


CANON_TENANT_BACKEND_CLOCK_POLICY = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError('datetime is required')
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('datetime must be timezone-aware')
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ClockObservation:
    observed_at: datetime
    backend_now: datetime | None = None

    def validate(self) -> None:
        ensure_aware(self.observed_at)
        if self.backend_now is not None:
            ensure_aware(self.backend_now)


@dataclass(frozen=True)
class TenantBackendClockPolicy:
    skew_tolerance_seconds: int = 15
    expiration_safety_margin_seconds: int = 2

    def validate(self) -> None:
        if int(self.skew_tolerance_seconds) < 0:
            raise ValueError('skew_tolerance_seconds must be >= 0')
        if int(self.expiration_safety_margin_seconds) < 0:
            raise ValueError('expiration_safety_margin_seconds must be >= 0')

    def normalize(self, value: datetime) -> datetime:
        self.validate()
        return ensure_aware(value)

    def safe_expiration(self, *, now: datetime, ttl_seconds: int) -> datetime:
        self.validate()
        if int(ttl_seconds) <= 0:
            raise ValueError('ttl_seconds must be > 0')
        return self.normalize(now) + timedelta(seconds=int(ttl_seconds) + int(self.expiration_safety_margin_seconds))

    def is_expired(self, *, expires_at: datetime, now: datetime | None = None) -> bool:
        self.validate()
        moment = self.normalize(now or utc_now())
        deadline = self.normalize(expires_at)
        return deadline <= moment

    def should_reap(self, *, expires_at: datetime, now: datetime | None = None) -> bool:
        self.validate()
        moment = self.normalize(now or utc_now())
        deadline = self.normalize(expires_at)
        return deadline <= (moment - timedelta(seconds=int(self.expiration_safety_margin_seconds)))

    def drift_seconds(self, observation: ClockObservation) -> float:
        self.validate()
        observation.validate()
        if observation.backend_now is None:
            return 0.0
        return float((ensure_aware(observation.backend_now) - ensure_aware(observation.observed_at)).total_seconds())

    def assert_backend_clock(self, observation: ClockObservation) -> None:
        drift = abs(self.drift_seconds(observation))
        if drift > float(self.skew_tolerance_seconds):
            raise RuntimeError(
                f'backend clock skew exceeded tolerance: drift={drift:.3f}s tolerance={self.skew_tolerance_seconds}s'
            )


class TenantBackendClockReader(Protocol):
    def read_backend_clock(self) -> datetime: ...


__all__ = [
    'CANON_TENANT_BACKEND_CLOCK_POLICY',
    'ClockObservation',
    'TenantBackendClockPolicy',
    'TenantBackendClockReader',
    'ensure_aware',
    'utc_now',
]

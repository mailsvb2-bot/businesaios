from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping


CANON_CREDENTIAL_ROTATION_POLICY = True


@dataclass(frozen=True)
class RotationDecision:
    should_rotate: bool
    reason: str
    next_rotation_at: datetime | None = None
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CredentialRotationPolicy:
    max_age_days: int = 90
    rotate_on_compromise: bool = True
    rotate_on_scope_change: bool = True
    min_remaining_ttl_seconds: int = 3600

    def validate(self) -> None:
        if int(self.max_age_days) <= 0:
            raise ValueError('max_age_days must be > 0')
        if int(self.min_remaining_ttl_seconds) < 0:
            raise ValueError('min_remaining_ttl_seconds must be >= 0')

    def evaluate(
        self,
        *,
        created_at: datetime,
        expires_at: datetime | None,
        compromised: bool = False,
        scope_changed: bool = False,
        now: datetime,
    ) -> RotationDecision:
        self.validate()
        if created_at.tzinfo is None or now.tzinfo is None:
            raise ValueError('timestamps must be timezone-aware')
        if now < created_at:
            raise ValueError('now must be >= created_at')
        if compromised and self.rotate_on_compromise:
            return RotationDecision(should_rotate=True, reason='compromised', next_rotation_at=now)
        if scope_changed and self.rotate_on_scope_change:
            return RotationDecision(should_rotate=True, reason='scope_changed', next_rotation_at=now)
        if now - created_at >= timedelta(days=int(self.max_age_days)):
            return RotationDecision(should_rotate=True, reason='max_age_exceeded', next_rotation_at=now)
        if expires_at is not None:
            if expires_at.tzinfo is None:
                raise ValueError('expires_at must be timezone-aware')
            remaining = expires_at - now
            if remaining.total_seconds() <= int(self.min_remaining_ttl_seconds):
                return RotationDecision(should_rotate=True, reason='ttl_low', next_rotation_at=now)
            return RotationDecision(
                should_rotate=False,
                reason='healthy',
                next_rotation_at=expires_at - timedelta(seconds=int(self.min_remaining_ttl_seconds)),
            )
        return RotationDecision(should_rotate=False, reason='healthy')


__all__ = [
    'CANON_CREDENTIAL_ROTATION_POLICY',
    'CredentialRotationPolicy',
    'RotationDecision',
]

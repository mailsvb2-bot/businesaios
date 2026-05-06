from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping


CANON_SESSION_POLICY = True


@dataclass(frozen=True)
class SessionVerdict:
    allowed: bool
    reason: str
    rotate_session: bool = False
    invalidate_session: bool = False
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionPolicy:
    max_idle_seconds: int = 3600
    max_absolute_seconds: int = 86400
    require_bound_ip: bool = False
    require_bound_user_agent: bool = False
    require_mfa: bool = False

    def validate(self) -> None:
        if int(self.max_idle_seconds) <= 0:
            raise ValueError('max_idle_seconds must be > 0')
        if int(self.max_absolute_seconds) <= 0:
            raise ValueError('max_absolute_seconds must be > 0')

    def evaluate(
        self,
        *,
        created_at: datetime,
        last_seen_at: datetime,
        now: datetime,
        expected_ip: str | None = None,
        observed_ip: str | None = None,
        expected_user_agent: str | None = None,
        observed_user_agent: str | None = None,
        revoked_at: datetime | None = None,
        auth_level: str | None = None,
        mfa_verified_at: datetime | None = None,
    ) -> SessionVerdict:
        self.validate()
        if created_at.tzinfo is None or last_seen_at.tzinfo is None or now.tzinfo is None:
            raise ValueError('timestamps must be timezone-aware')
        if revoked_at is not None and revoked_at.tzinfo is None:
            raise ValueError('revoked_at must be timezone-aware')
        if mfa_verified_at is not None and mfa_verified_at.tzinfo is None:
            raise ValueError('mfa_verified_at must be timezone-aware')
        if last_seen_at < created_at:
            raise ValueError('last_seen_at must be >= created_at')
        if now < created_at:
            raise ValueError('now must be >= created_at')
        if revoked_at is not None and revoked_at <= now:
            return SessionVerdict(allowed=False, reason='session_revoked', invalidate_session=True)
        if now - last_seen_at > timedelta(seconds=int(self.max_idle_seconds)):
            return SessionVerdict(allowed=False, reason='idle_timeout', invalidate_session=True)
        if now - created_at > timedelta(seconds=int(self.max_absolute_seconds)):
            return SessionVerdict(allowed=False, reason='absolute_timeout', invalidate_session=True)
        if self.require_bound_ip and expected_ip and observed_ip and expected_ip != observed_ip:
            return SessionVerdict(allowed=False, reason='ip_mismatch', invalidate_session=True)
        if self.require_bound_user_agent and expected_user_agent and observed_user_agent and expected_user_agent != observed_user_agent:
            return SessionVerdict(allowed=False, reason='user_agent_mismatch', invalidate_session=True)
        if self.require_mfa and (auth_level or '').lower() != 'mfa' and mfa_verified_at is None:
            return SessionVerdict(allowed=False, reason='mfa_required', invalidate_session=True)
        remaining = timedelta(seconds=int(self.max_absolute_seconds)) - (now - created_at)
        rotate = remaining.total_seconds() < max(300, int(self.max_idle_seconds) // 2)
        labels: dict[str, str] = {}
        if mfa_verified_at is not None:
            labels['mfa'] = 'verified'
        elif (auth_level or '').strip():
            labels['auth_level'] = str(auth_level)
        return SessionVerdict(allowed=True, reason='ok', rotate_session=rotate, labels=labels)


__all__ = [
    'CANON_SESSION_POLICY',
    'SessionPolicy',
    'SessionVerdict',
]

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping


CANON_TOKEN_POLICY = True


@dataclass(frozen=True)
class TokenVerdict:
    allowed: bool
    reason: str
    requires_reissue: bool = False
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenPolicy:
    max_ttl_seconds: int = 3600
    required_scopes: tuple[str, ...] = ()
    allow_clock_skew_seconds: int = 30
    require_subject: bool = True
    require_audience: bool = True
    require_issuer: bool = False
    require_session_id: bool = False
    allowed_algorithms: tuple[str, ...] = ('HS256', 'RS256', 'ES256')

    def validate(self) -> None:
        if int(self.max_ttl_seconds) <= 0:
            raise ValueError('max_ttl_seconds must be > 0')
        if int(self.allow_clock_skew_seconds) < 0:
            raise ValueError('allow_clock_skew_seconds must be >= 0')

    def evaluate(
        self,
        *,
        issued_at: datetime,
        expires_at: datetime,
        now: datetime,
        scopes: tuple[str, ...] = (),
        subject: str | None = None,
        audience: str | None = None,
        issuer: str | None = None,
        not_before: datetime | None = None,
        token_id: str | None = None,
        session_id: str | None = None,
        algorithm: str | None = None,
        key_id: str | None = None,
    ) -> TokenVerdict:
        self.validate()
        if issued_at.tzinfo is None or expires_at.tzinfo is None or now.tzinfo is None:
            raise ValueError('timestamps must be timezone-aware')
        if not_before is not None and not_before.tzinfo is None:
            raise ValueError('not_before must be timezone-aware')
        if self.require_subject and not str(subject or '').strip():
            return TokenVerdict(allowed=False, reason='missing_subject')
        if self.require_audience and not str(audience or '').strip():
            return TokenVerdict(allowed=False, reason='missing_audience')
        if self.require_issuer and not str(issuer or '').strip():
            return TokenVerdict(allowed=False, reason='missing_issuer')
        if self.require_session_id and not str(session_id or '').strip():
            return TokenVerdict(allowed=False, reason='missing_session_id')
        if algorithm is not None and str(algorithm) not in set(self.allowed_algorithms):
            return TokenVerdict(allowed=False, reason='algorithm_not_allowed')
        if expires_at <= issued_at:
            return TokenVerdict(allowed=False, reason='invalid_lifetime')
        if expires_at - issued_at > timedelta(seconds=int(self.max_ttl_seconds)):
            return TokenVerdict(allowed=False, reason='ttl_exceeds_policy')
        skew = timedelta(seconds=int(self.allow_clock_skew_seconds))
        if now < issued_at - skew:
            return TokenVerdict(allowed=False, reason='used_before_issue_time')
        if not_before is not None and now < not_before - skew:
            return TokenVerdict(allowed=False, reason='not_before_violation')
        if now > expires_at + skew:
            return TokenVerdict(allowed=False, reason='expired', requires_reissue=True)
        missing_scopes = tuple(scope for scope in self.required_scopes if scope not in set(scopes))
        if missing_scopes:
            return TokenVerdict(allowed=False, reason='missing_scope', labels={'missing_scopes': ','.join(missing_scopes)})
        remaining = expires_at - now
        labels: dict[str, str] = {}
        if token_id:
            labels['token_id'] = str(token_id)
        if session_id:
            labels['session_id'] = str(session_id)
        if key_id:
            labels['key_id'] = str(key_id)
        requires_reissue = remaining.total_seconds() < max(60, int(self.max_ttl_seconds) // 10)
        return TokenVerdict(allowed=True, reason='ok', requires_reissue=requires_reissue, labels=labels)


__all__ = [
    'CANON_TOKEN_POLICY',
    'TokenPolicy',
    'TokenVerdict',
]

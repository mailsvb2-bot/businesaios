from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class CrmAccessToken:
    access_token: str
    token_type: str = 'Bearer'
    expires_at: datetime | None = None
    refresh_token: str | None = None
    scope: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def is_expired(self, *, skew_seconds: int = 30, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        current = now or datetime.now(timezone.utc)
        return current + timedelta(seconds=skew_seconds) >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            'access_token': self.access_token,
            'token_type': self.token_type,
            'expires_at': self.expires_at.isoformat() if self.expires_at is not None else None,
            'refresh_token': self.refresh_token,
            'scope': list(self.scope),
            'metadata': dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'CrmAccessToken':
        expires_at_raw = payload.get('expires_at')
        expires_at = None
        if isinstance(expires_at_raw, str) and expires_at_raw.strip():
            expires_at = datetime.fromisoformat(expires_at_raw)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        scope_raw = payload.get('scope')
        if isinstance(scope_raw, (list, tuple)):
            scope = tuple(str(item) for item in scope_raw if str(item).strip())
        elif isinstance(scope_raw, str):
            scope = tuple(item for item in scope_raw.replace(',', ' ').split() if item)
        else:
            scope = ()
        metadata = payload.get('metadata')
        return cls(
            access_token=str(payload.get('access_token') or ''),
            token_type=str(payload.get('token_type') or 'Bearer'),
            expires_at=expires_at,
            refresh_token=str(payload.get('refresh_token') or '') or None,
            scope=scope,
            metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
        )

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol


CANON_ADS_TOKEN_STORE_CONTRACT = True


def _clean(value: object, *, field_name: str) -> str:
    text = str(value or '').strip()
    if not text:
        raise ValueError(f'{field_name} is required')
    return text


def _parse_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class TokenStoreKey:
    tenant_id: str
    platform: str
    account_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, 'tenant_id', _clean(self.tenant_id, field_name='tenant_id'))
        object.__setattr__(self, 'platform', _clean(self.platform, field_name='platform'))
        object.__setattr__(self, 'account_id', _clean(self.account_id, field_name='account_id'))

    def as_dict(self) -> dict[str, str]:
        return {
            'tenant_id': str(self.tenant_id),
            'platform': str(self.platform),
            'account_id': str(self.account_id),
        }


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    refresh_token: Optional[str] = None
    expires_at_iso: Optional[str] = None
    token_type: str = 'Bearer'
    scope: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, 'access_token', _clean(self.access_token, field_name='access_token'))
        token_type = str(self.token_type or 'Bearer').strip() or 'Bearer'
        object.__setattr__(self, 'token_type', token_type)
        if self.refresh_token is not None:
            refresh = str(self.refresh_token).strip()
            object.__setattr__(self, 'refresh_token', refresh or None)
        if self.scope is not None:
            scope = str(self.scope).strip()
            object.__setattr__(self, 'scope', scope or None)
        if self.expires_at_iso is not None:
            parsed = _parse_iso(self.expires_at_iso)
            object.__setattr__(self, 'expires_at_iso', parsed.isoformat() if parsed is not None else None)

    @property
    def expires_at(self) -> datetime | None:
        return _parse_iso(self.expires_at_iso)

    def is_expired(self, *, at: datetime | None = None, skew_seconds: int = 0) -> bool:
        expires_at = self.expires_at
        if expires_at is None:
            return False
        now = at or datetime.now(timezone.utc)
        return now.timestamp() + max(0, int(skew_seconds)) >= expires_at.timestamp()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdsTokenStore(Protocol):
    """Tenant-scoped OAuth token storage.

    This protocol intentionally stays minimal so storage can be backed by sqlite,
    vault, KMS, or a remote secret service without duplicating logic elsewhere.
    """

    def ensure_schema(self) -> None: ...

    def put(self, *, tenant_id: str, platform: str, account_id: str, token: OAuthToken) -> None: ...

    def get(self, *, tenant_id: str, platform: str, account_id: str) -> Optional[OAuthToken]: ...

    def delete(self, *, tenant_id: str, platform: str, account_id: str) -> None: ...


class SecretVault(Protocol):
    """Minimal secret provider (env/file/KMS)."""

    def get_secret(self, key: str) -> str: ...


__all__ = [
    'AdsTokenStore',
    'CANON_ADS_TOKEN_STORE_CONTRACT',
    'OAuthToken',
    'SecretVault',
    'TokenStoreKey',
]

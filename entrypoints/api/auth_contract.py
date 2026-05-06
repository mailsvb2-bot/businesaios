from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Protocol

from governance.rbac_contract import RoleId


CANON_API_AUTH_CONTRACT = True
CANON_API_FINAL_OWNER = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuthMechanism(str, Enum):
    NONE = 'none'
    API_KEY = 'api_key'
    JWT = 'jwt'
    SERVICE = 'service'


@dataclass(frozen=True)
class AuthPrincipal:
    subject: str
    tenant_id: str | None = None
    actor_id: str | None = None
    session_id: str | None = None
    roles: tuple[RoleId, ...] = ()
    scopes: tuple[str, ...] = ()
    audience: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.subject or '').strip():
            raise ValueError('subject is required')
        if self.tenant_id is not None and not str(self.tenant_id).strip():
            raise ValueError('tenant_id must not be blank when provided')
        if self.actor_id is not None and not str(self.actor_id).strip():
            raise ValueError('actor_id must not be blank when provided')
        if self.session_id is not None and not str(self.session_id).strip():
            raise ValueError('session_id must not be blank when provided')
        if self.audience is not None and not str(self.audience).strip():
            raise ValueError('audience must not be blank when provided')


@dataclass(frozen=True)
class AuthVerdict:
    allowed: bool
    reason: str
    mechanism: AuthMechanism = AuthMechanism.NONE
    principal: AuthPrincipal | None = None
    challenge: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.reason or '').strip():
            raise ValueError('reason is required')
        if self.allowed and self.principal is None:
            raise ValueError('principal is required for allowed verdict')
        if self.principal is not None:
            self.principal.validate()


@dataclass(frozen=True)
class RequestAuthentication:
    tenant_id: str | None = None
    authorization: str | None = None
    api_key: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    remote_ip: str | None = None
    user_agent: str | None = None
    extra_headers: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        for name, value in (
            ('tenant_id', self.tenant_id),
            ('request_id', self.request_id),
            ('correlation_id', self.correlation_id),
            ('remote_ip', self.remote_ip),
            ('user_agent', self.user_agent),
        ):
            if value is not None and not str(value).strip():
                raise ValueError(f'{name} must not be blank when provided')


class AuthPolicy(Protocol):
    def authenticate(self, request: RequestAuthentication) -> AuthVerdict: ...


__all__ = [
    'AuthMechanism',
    'AuthPolicy',
    'AuthPrincipal',
    'AuthVerdict',
    'CANON_API_AUTH_CONTRACT',
    'RequestAuthentication',
    'utc_now',
]

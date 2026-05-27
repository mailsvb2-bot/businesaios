from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Protocol

from core.tenancy.scope import TenantId


@dataclass(frozen=True)
class AuthContext:
    tenant_id: TenantId
    subject: str  # user_id / service_id
    scopes: tuple[str, ...] = ()
    claims: Dict[str, Any] | None = None

    def has_scope(self, scope: str) -> bool:
        s = (scope or "").strip()
        if not s:
            return False
        return s in set(self.scopes)

    def has_any_scope(self, scopes: Iterable[str]) -> bool:
        return any(self.has_scope(scope) for scope in scopes)


class AuthProvider(Protocol):
    """Extract auth context from a transport-specific request context."""

    def authenticate(self, request_ctx: Any) -> Optional[AuthContext]: ...


class AuthRequired(RuntimeError):
    pass


class AuthForbidden(RuntimeError):
    pass


def require_auth(ctx: Optional[AuthContext]) -> AuthContext:
    if ctx is None:
        raise AuthRequired("AUTH_REQUIRED")
    if not str(ctx.subject or "").strip():
        raise AuthRequired("AUTH_EMPTY_SUBJECT")
    return ctx


def require_scope(ctx: Optional[AuthContext], scope: str) -> AuthContext:
    auth = require_auth(ctx)
    normalized = str(scope or "").strip()
    if not normalized:
        raise AuthForbidden("AUTH_SCOPE_REQUIRED")
    if not auth.has_scope(normalized):
        raise AuthForbidden(f"AUTH_SCOPE_FORBIDDEN:{normalized}")
    return auth

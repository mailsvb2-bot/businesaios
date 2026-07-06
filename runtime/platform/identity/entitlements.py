from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AuthContext:
    """Minimal identity context, strictly tenant-scoped."""

    tenant_id: str
    user_id: str
    is_authenticated: bool


class IdentityProvider(Protocol):
    """Resolve auth state for a user (platform concern)."""

    def resolve(self, *, tenant_id: str, user_id: str) -> AuthContext: ...


class EntitlementsProvider(Protocol):
    """Entitlements are tenant-scoped. Storage is implementation-defined."""

    def has(self, *, tenant_id: str, user_id: str, entitlement: str) -> bool: ...

    def list(self, *, tenant_id: str, user_id: str) -> tuple[str, ...]: ...


class InMemoryIdentityProvider:
    """Safe default for tests/local. Production must bind a real provider."""

    def __init__(self, *, authenticated_users: set[tuple[str, str]] | None = None) -> None:
        self._authed = authenticated_users or set()

    def resolve(self, *, tenant_id: str, user_id: str) -> AuthContext:
        return AuthContext(
            tenant_id=tenant_id,
            user_id=user_id,
            is_authenticated=(tenant_id, user_id) in self._authed,
        )


class InMemoryEntitlementsProvider:
    """Safe default for tests/local."""

    def __init__(self, *, grants: Mapping[tuple[str, str], Iterable[str]] | None = None) -> None:
        self._grants: dict[tuple[str, str], set[str]] = {}
        if grants:
            for k, v in grants.items():
                self._grants[k] = set(v)

    def has(self, *, tenant_id: str, user_id: str, entitlement: str) -> bool:
        return entitlement in self._grants.get((tenant_id, user_id), set())

    def list(self, *, tenant_id: str, user_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._grants.get((tenant_id, user_id), set())))


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str
    missing_entitlements: tuple[str, ...] = ()


class AccessController:
    """Single enforcement point.

    - Auth gate
    - Entitlement gates
    """

    def __init__(self, *, identity: IdentityProvider, entitlements: EntitlementsProvider) -> None:
        self._identity = identity
        self._entitlements = entitlements

    def check_access(
        self,
        *,
        tenant_id: str,
        user_id: str,
        requires_auth: bool,
        required_entitlements: Sequence[str],
    ) -> AccessDecision:
        auth = self._identity.resolve(tenant_id=tenant_id, user_id=user_id)
        if requires_auth and not auth.is_authenticated:
            return AccessDecision(allowed=False, reason="auth_required")

        missing = [
            e
            for e in required_entitlements
            if not self._entitlements.has(tenant_id=tenant_id, user_id=user_id, entitlement=e)
        ]
        if missing:
            return AccessDecision(
                allowed=False,
                reason="entitlement_missing",
                missing_entitlements=tuple(sorted(missing)),
            )

        return AccessDecision(allowed=True, reason="ok")

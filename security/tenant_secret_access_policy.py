from __future__ import annotations

from dataclasses import dataclass


CANON_TENANT_SECRET_ACCESS_POLICY = True


@dataclass(frozen=True)
class TenantSecretAccessVerdict:
    allowed: bool
    reason: str


class TenantSecretAccessPolicy:
    """Fail-closed tenant isolation policy for secret scopes."""

    def evaluate(self, *, requester_tenant_id: str, secret_scope: str) -> TenantSecretAccessVerdict:
        prefix = f"tenant:{str(requester_tenant_id).strip()}:"
        if str(secret_scope).startswith(prefix):
            return TenantSecretAccessVerdict(True, 'tenant scope matches')
        return TenantSecretAccessVerdict(False, 'cross-tenant secret access denied')


__all__ = [
    'CANON_TENANT_SECRET_ACCESS_POLICY',
    'TenantSecretAccessPolicy',
    'TenantSecretAccessVerdict',
]

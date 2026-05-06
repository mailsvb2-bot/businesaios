from __future__ import annotations


CANON_TENANT_SECRET_SCOPE = True


class TenantSecretScope:
    """Canonical tenant namespace owner for secrets."""

    def build_scope(self, *, tenant_id: str, local_scope: str) -> str:
        tenant = str(tenant_id or '').strip()
        local = str(local_scope or '').strip()
        if not tenant:
            raise ValueError('tenant_id is required')
        if not local:
            raise ValueError('local_scope is required')
        return f'tenant:{tenant}:{local}'


__all__ = [
    'CANON_TENANT_SECRET_SCOPE',
    'TenantSecretScope',
]

from __future__ import annotations

from core.tenancy.scope import TenantScope


def current_tenant_id() -> str:
    """Return tenant_id for this process.

    Strict mode: TENANT_ID must be set in environment (or injected by boot).
    """
    return TenantScope.from_env().tenant_id

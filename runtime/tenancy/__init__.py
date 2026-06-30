"""Canonical runtime tenancy normalization surface.

Runtime code may normalize and validate tenant identifiers through this module
without binding itself to core tenancy internals.
"""

from __future__ import annotations

from runtime.public_api_alias import install_public_api_alias


from core.tenancy.normalization import (
    UNKNOWN_TENANT_ID,
    is_placeholder_tenant_id,
    normalize_tenant_id,
    normalize_tenant_id_or_unknown,
    normalize_tenant_scope,
    require_tenant_id,
)
from core.tenancy.scope import TenantId, TenantScope, as_tenant_id
from core.tenancy.tenant import current_tenant_id
from runtime.tenancy.contract import RUNTIME_TENANCY_PUBLIC_API, TENANCY_NORMALIZATION_CANON

__all__ = [
    'CANON_RUNTIME_TENANCY_NAMESPACE',
    "RUNTIME_TENANCY_PUBLIC_API",
    "TENANCY_NORMALIZATION_CANON",
    "UNKNOWN_TENANT_ID",
    "TenantId",
    "TenantScope",
    "as_tenant_id",
    "current_tenant_id",
    "is_placeholder_tenant_id",
    "normalize_tenant_id",
    "normalize_tenant_id_or_unknown",
    "normalize_tenant_scope",
    "require_tenant_id",
]

CANON_RUNTIME_TENANCY_NAMESPACE = True



install_public_api_alias(__name__)

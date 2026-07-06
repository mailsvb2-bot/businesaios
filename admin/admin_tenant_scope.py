"""Admin tenant-scope normalization helpers.

The admin read-model layer needs a tiny, deterministic tenant boundary helper.
This module is data/normalization only: it does not create a second decision
path, issue actions, or perform side effects.
"""

from __future__ import annotations

CANON_ADMIN_TENANT_SCOPE = True
DEFAULT_ADMIN_TENANT_ID = "default"


def normalize_admin_tenant_id(value: object, *, default: str = DEFAULT_ADMIN_TENANT_ID) -> str:
    tenant_id = str(value or "").strip()
    if tenant_id:
        return tenant_id
    fallback = str(default or "").strip()
    return fallback or DEFAULT_ADMIN_TENANT_ID


__all__ = [
    "CANON_ADMIN_TENANT_SCOPE",
    "DEFAULT_ADMIN_TENANT_ID",
    "normalize_admin_tenant_id",
]

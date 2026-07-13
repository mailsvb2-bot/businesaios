from __future__ import annotations

from typing import Any


def assert_payment_metadata_tenant(
    metadata: dict[str, Any] | None,
    *,
    tenant_id: str,
    external_id: str,
) -> dict[str, Any]:
    scoped = dict(metadata or {})
    recorded_tenant = str(scoped.get("tenant_id") or "").strip()
    tenant = str(tenant_id or "").strip()
    if recorded_tenant and recorded_tenant != tenant:
        raise RuntimeError(
            f"PAYMENT_METADATA_TENANT_MISMATCH:{external_id}:"
            f"recorded={recorded_tenant}:runtime={tenant}"
        )
    scoped["tenant_id"] = tenant
    return scoped


def resolve_payment_user(
    context: dict[str, Any],
    *,
    user_id_hint: str | None,
    external_id: str,
) -> str:
    owner = str(context.get("user_id") or "").strip()
    if not owner:
        raise RuntimeError(f"PAYMENT_USER_CONTEXT_NOT_FOUND:{external_id}")
    hinted = str(user_id_hint or "").strip()
    if hinted and hinted != owner:
        raise RuntimeError(
            f"PAYMENT_USER_CONTEXT_MISMATCH:{external_id}:"
            f"recorded={owner}:hint={hinted}"
        )
    return owner


__all__ = ["assert_payment_metadata_tenant", "resolve_payment_user"]

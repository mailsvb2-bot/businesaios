from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope


def build_trace_group_key(*, tenant_id: str, user_id: str, correlation_id: str) -> tuple[str, str, str]:
    return (normalize_tenant_scope(tenant_id, allow_unknown=True), str(user_id), str(correlation_id))

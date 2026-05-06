from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope


def read_messaging_policy_snapshot(*, read_service, tenant_id: str, user_id: str, correlation_id: str) -> dict | None:
    tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
    snap = read_service.get_snapshot(tenant_id=tenant_scope, user_id=str(user_id), correlation_id=str(correlation_id))
    if snap is None:
        return None
    if isinstance(snap, dict):
        out = dict(snap)
        out['tenant_id'] = normalize_tenant_scope(out.get('tenant_id') or tenant_scope, allow_unknown=True)
        return out
    return {
        'tenant_id': normalize_tenant_scope(snap.tenant_id, allow_unknown=True),
        'user_id': snap.user_id,
        'correlation_id': snap.correlation_id,
        'delivered': list(snap.delivered),
        'failed': list(snap.failed),
        'blocked': list(snap.blocked),
        'last_plan_channels': list(snap.last_plan_channels),
        'last_selected_channel': snap.last_selected_channel,
        'last_terminal_reason': snap.last_terminal_reason,
        'attempts_count': snap.attempts_count,
    }

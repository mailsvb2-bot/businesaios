from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope


def build_alert_notification_dedup_key(*, tenant_id: str, recipient_user_id: str, channel: str, alert_code: str, affected_user_id: str, business_id: str = "") -> str:
    tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
    parts = [tenant_scope, str(recipient_user_id), str(channel), str(alert_code), str(affected_user_id)]
    business_scope = str(business_id or "").strip()
    return "|".join(parts if not business_scope else [tenant_scope, business_scope, *parts[1:]])

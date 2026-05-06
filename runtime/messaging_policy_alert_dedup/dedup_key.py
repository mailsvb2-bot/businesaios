from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope


def build_alert_notification_dedup_key(*, tenant_id: str, recipient_user_id: str, channel: str, alert_code: str, affected_user_id: str) -> str:
    return "|".join([normalize_tenant_scope(tenant_id, allow_unknown=True), str(recipient_user_id), str(channel), str(alert_code), str(affected_user_id)])

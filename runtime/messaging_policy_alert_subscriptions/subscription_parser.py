from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope
from runtime.messaging_policy_alert_subscriptions.subscription_record import AlertSubscriptionRecord


def parse_subscription(value: dict | None, *, tenant_id: str) -> AlertSubscriptionRecord | None:
    if not isinstance(value, dict):
        return None
    recipient_user_id = str(value.get("recipient_user_id") or "").strip()
    if not recipient_user_id:
        return None
    tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
    return AlertSubscriptionRecord(tenant_id=tenant_scope, recipient_user_id=recipient_user_id, channel=str(value.get("channel") or "telegram"), min_level=str(value.get("min_level") or "warn"), enabled=bool(value.get("enabled", True)), code_filters=tuple(value.get("code_filters") or ()), user_scope=tuple(value.get("user_scope") or ()))

from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.subscription_collection import parse_subscription_list


def canonical_alert_subscriptions_value(value, *, tenant_id: str) -> list[dict]:
    items = parse_subscription_list(value, tenant_id=str(tenant_id))
    return [{"recipient_user_id": item.recipient_user_id, "channel": item.channel, "min_level": item.min_level, "enabled": item.enabled, "code_filters": list(item.code_filters), "user_scope": list(item.user_scope)} for item in items]

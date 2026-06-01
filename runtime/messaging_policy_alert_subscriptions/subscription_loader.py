from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.settings_key import SETTING_KEY
from runtime.messaging_policy_alert_subscriptions.subscription_collection import parse_subscription_list
from runtime.tenancy import normalize_tenant_scope


def load_alert_subscriptions(*, settings_gateway, tenant_id: str) -> tuple:
    if settings_gateway is None:
        return ()
    tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
    value = settings_gateway.get_value(tenant_id=tenant_scope, key=SETTING_KEY)
    return parse_subscription_list(value, tenant_id=tenant_scope)

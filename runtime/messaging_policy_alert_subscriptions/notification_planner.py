from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope
from runtime.messaging_policy_alert_subscriptions.notification_item import AlertNotificationItem
from runtime.messaging_policy_alert_subscriptions.notification_plan import AlertNotificationPlan
from runtime.messaging_policy_alert_subscriptions.notification_text_builder import build_alert_notification_text


class AlertNotificationPlanner:
    def build_plan(self, *, tenant_id: str, affected_user_id: str, alerts, subscriptions, date_from: str, date_to: str, match_service) -> AlertNotificationPlan:
        tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
        matched = match_service.match(subscriptions=subscriptions, alerts=alerts, affected_user_id=str(affected_user_id or ""))
        by_code = {str(item.code): item for item in tuple(alerts or ())}
        items = []
        for item in tuple(matched or ()):
            alert_item = by_code.get(str(item.alert_code))
            if alert_item is None:
                continue
            items.append(AlertNotificationItem(tenant_id=tenant_scope, recipient_user_id=item.recipient_user_id, channel=item.channel, text=build_alert_notification_text(alert_item=alert_item, tenant_id=tenant_scope, affected_user_id=str(affected_user_id or ""), date_from=str(date_from or ""), date_to=str(date_to or "")), alert_code=item.alert_code, alert_level=item.alert_level, affected_user_id=item.affected_user_id))
        return AlertNotificationPlan(items=tuple(items))

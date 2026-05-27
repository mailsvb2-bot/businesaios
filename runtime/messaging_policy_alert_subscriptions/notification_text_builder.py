from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.notification_text_parts import (
    context_line,
    detail_line,
    headline,
    metric_line,
)


def build_alert_notification_text(*, alert_item, tenant_id: str, affected_user_id: str, date_from: str, date_to: str) -> str:
    return "\n".join([headline(level=alert_item.level, code=alert_item.code), detail_line(title=alert_item.title, detail=alert_item.detail), metric_line(metric_name=alert_item.metric_name, metric_value=alert_item.metric_value, threshold_value=alert_item.threshold_value), context_line(tenant_id=tenant_id, user_id=affected_user_id, date_from=date_from, date_to=date_to)])

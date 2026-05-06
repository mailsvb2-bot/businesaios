from __future__ import annotations

from runtime.messaging_policy_alerts.alert_item import MessagingPolicyAlertItem


def build_alert(*, code: str, level: str, title: str, detail: str, metric_name: str, metric_value: float, threshold_value: float) -> MessagingPolicyAlertItem:
    return MessagingPolicyAlertItem(
        code=str(code),
        level=str(level),
        title=str(title),
        detail=str(detail),
        metric_name=str(metric_name),
        metric_value=float(metric_value),
        threshold_value=float(threshold_value),
    )

from __future__ import annotations

from runtime.messaging_policy_alert_dedup_persistent.boot_tenant_aware import build_tenant_aware_persistent_deduping_alert_notifier
from runtime.messaging_policy_alert_subscriptions.service import MessagingPolicyAlertSubscriptionService


def build_persistent_alert_subscription_service_v2(*, alert_service, settings_gateway, cooldown_s: int = 3600):
    stack = build_tenant_aware_persistent_deduping_alert_notifier(
        settings_gateway=settings_gateway,
        cooldown_s=int(cooldown_s),
    )
    return MessagingPolicyAlertSubscriptionService(
        alert_service=alert_service,
        notifier=stack['notifier'],
    )

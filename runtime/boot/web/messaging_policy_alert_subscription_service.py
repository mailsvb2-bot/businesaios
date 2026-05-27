from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from runtime.messaging_policy_alert_dedup.boot import build_deduping_alert_notifier
from runtime.messaging_policy_alert_dedup_persistent.boot_tenant_aware import (
    build_tenant_aware_persistent_deduping_alert_notifier,
)
from runtime.messaging_policy_alert_subscriptions.service import MessagingPolicyAlertSubscriptionService


def build_messaging_policy_alert_subscription_service(*, alert_service, settings_gateway=None, tenant_id: str = '', cooldown_s: int = 3600):
    if settings_gateway is None:
        dedup_stack = build_deduping_alert_notifier(cooldown_s=int(cooldown_s))
    else:
        dedup_stack = build_tenant_aware_persistent_deduping_alert_notifier(
            settings_gateway=settings_gateway,
            cooldown_s=int(cooldown_s),
        )
    service = MessagingPolicyAlertSubscriptionService(
        alert_service=alert_service,
        notifier=dedup_stack['notifier'],
    )
    return {'service': service, 'notifier_stack': dedup_stack}

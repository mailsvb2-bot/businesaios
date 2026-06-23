from __future__ import annotations

from runtime.messaging_policy_alert_dedup_persistent.tenant_mark_sent_service import (
    TenantAwareAlertNotificationMarkSentService,
)
from runtime.messaging_policy_alert_dedup_persistent.tenant_notifier import (
    TenantAwareDedupingMessagingPolicyAlertNotifier,
)
from runtime.messaging_policy_alert_dedup_persistent.tenant_store_factory import TenantScopedDedupStoreFactory
from runtime.messaging_policy_alert_dedup_persistent.tenant_suppression_service import (
    TenantAwareAlertNotificationSuppressionService,
)
from runtime.messaging_policy_alert_subscriptions.notifier import MessagingPolicyAlertNotifier


def build_tenant_aware_persistent_deduping_alert_notifier(*, settings_gateway, cooldown_s: int = 3600, tenant_id: str = ''):
    store_factory = TenantScopedDedupStoreFactory(settings_gateway=settings_gateway)
    suppression_service = TenantAwareAlertNotificationSuppressionService(
        store_factory=store_factory,
        cooldown_s=int(cooldown_s),
        tenant_id=tenant_id,
    )
    mark_sent_service = TenantAwareAlertNotificationMarkSentService(store_factory=store_factory)
    base_notifier = MessagingPolicyAlertNotifier()
    return {
        'store': store_factory,
        'store_factory': store_factory,
        'suppression_service': suppression_service,
        'mark_sent_service': mark_sent_service,
        'notifier': TenantAwareDedupingMessagingPolicyAlertNotifier(
            base_notifier=base_notifier,
            suppression_service=suppression_service,
            mark_sent_service=mark_sent_service,
        ),
    }

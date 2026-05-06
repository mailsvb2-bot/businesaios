from __future__ import annotations

from runtime.messaging_policy_alert_dedup.inmemory_store import InMemoryAlertNotificationDedupStore
from runtime.messaging_policy_alert_dedup.mark_sent_service import AlertNotificationMarkSentService
from runtime.messaging_policy_alert_dedup.notifier import DedupingMessagingPolicyAlertNotifier
from runtime.messaging_policy_alert_dedup.suppression_service import AlertNotificationSuppressionService
from runtime.messaging_policy_alert_subscriptions.notifier import MessagingPolicyAlertNotifier


def build_deduping_alert_notifier(*, cooldown_s: int = 3600):
    store = InMemoryAlertNotificationDedupStore()
    suppression_service = AlertNotificationSuppressionService(store=store, cooldown_s=int(cooldown_s))
    mark_sent_service = AlertNotificationMarkSentService(store=store)
    base_notifier = MessagingPolicyAlertNotifier()
    return {"store": store, "suppression_service": suppression_service, "mark_sent_service": mark_sent_service, "notifier": DedupingMessagingPolicyAlertNotifier(base_notifier=base_notifier, suppression_service=suppression_service, mark_sent_service=mark_sent_service)}

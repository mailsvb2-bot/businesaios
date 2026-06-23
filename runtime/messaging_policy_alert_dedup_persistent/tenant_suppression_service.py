from __future__ import annotations

from runtime.messaging_policy_alert_dedup.cooldown_seconds import DEFAULT_ALERT_NOTIFICATION_COOLDOWN_S
from runtime.messaging_policy_alert_dedup.dedup_key import build_alert_notification_dedup_key
from runtime.messaging_policy_alert_dedup.suppression_decision import AlertSuppressionDecision
from runtime.messaging_policy_alert_dedup.time_now import now_epoch_s


class TenantAwareAlertNotificationSuppressionService:
    def __init__(self, *, store_factory, cooldown_s: int = DEFAULT_ALERT_NOTIFICATION_COOLDOWN_S, tenant_id: str = ''):
        self._store_factory = store_factory
        self._cooldown_s = int(cooldown_s)
        self._store = store_factory.for_tenant(tenant_id=tenant_id)

    def evaluate(
        self,
        *,
        tenant_id: str,
        recipient_user_id: str,
        channel: str,
        alert_code: str,
        affected_user_id: str,
    ):
        dedup_key = build_alert_notification_dedup_key(
            tenant_id=tenant_id,
            recipient_user_id=recipient_user_id,
            channel=channel,
            alert_code=alert_code,
            affected_user_id=affected_user_id,
        )
        store = self._store_factory.for_tenant(tenant_id=tenant_id)
        record = store.get(dedup_key=dedup_key)
        if record is None:
            return dedup_key, AlertSuppressionDecision(should_send=True, reason='first_send')
        if int(now_epoch_s()) - int(record.sent_at_epoch_s) < int(self._cooldown_s):
            return dedup_key, AlertSuppressionDecision(should_send=False, reason='cooldown_active')
        return dedup_key, AlertSuppressionDecision(should_send=True, reason='cooldown_elapsed')

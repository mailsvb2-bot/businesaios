from __future__ import annotations

"""Alert notification suppression (cooldown/dedup)."""

from runtime.messaging_policy_alert_dedup.cooldown_check import is_in_cooldown
from runtime.messaging_policy_alert_dedup.cooldown_seconds import DEFAULT_ALERT_NOTIFICATION_COOLDOWN_S
from runtime.messaging_policy_alert_dedup.dedup_key import build_alert_notification_dedup_key
from runtime.messaging_policy_alert_dedup.suppression_decision import AlertSuppressionDecision
from runtime.messaging_policy_alert_dedup.time_now import now_epoch_s


class AlertNotificationSuppressionService:
    def __init__(self, *, store, cooldown_s: int = DEFAULT_ALERT_NOTIFICATION_COOLDOWN_S):
        self._store = store
        self._cooldown_s = int(cooldown_s)

    def evaluate(self, *, tenant_id: str, recipient_user_id: str, channel: str, alert_code: str, affected_user_id: str) -> tuple[str, AlertSuppressionDecision]:
        dedup_key = build_alert_notification_dedup_key(tenant_id=tenant_id, recipient_user_id=recipient_user_id, channel=channel, alert_code=alert_code, affected_user_id=affected_user_id)
        record = self._store.get(dedup_key=dedup_key)
        if record is None:
            return dedup_key, AlertSuppressionDecision(should_send=True, reason="first_send")
        current = now_epoch_s()
        if is_in_cooldown(last_sent_epoch_s=int(record.sent_at_epoch_s), now_epoch_s=current, cooldown_s=self._cooldown_s):
            return dedup_key, AlertSuppressionDecision(should_send=False, reason="cooldown_active")
        return dedup_key, AlertSuppressionDecision(should_send=True, reason="cooldown_elapsed")

    decide = evaluate

    issue = evaluate

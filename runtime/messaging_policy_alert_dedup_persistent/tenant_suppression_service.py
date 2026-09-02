from __future__ import annotations

from runtime.messaging_policy_alert_dedup.cooldown_seconds import DEFAULT_ALERT_NOTIFICATION_COOLDOWN_S
from runtime.messaging_policy_alert_dedup.dedup_key import build_alert_notification_dedup_key
from runtime.messaging_policy_alert_dedup.suppression_decision import AlertSuppressionDecision
from runtime.messaging_policy_alert_dedup.suppression_service import _approval_is_pending
from runtime.messaging_policy_alert_dedup.time_now import now_epoch_s


class TenantAwareAlertNotificationSuppressionService:
    def __init__(self, *, store_factory, cooldown_s: int = DEFAULT_ALERT_NOTIFICATION_COOLDOWN_S, tenant_id: str = '', approval_status_resolver=None):
        self._store_factory, self._store = store_factory, store_factory.for_tenant(tenant_id=tenant_id)
        self._cooldown_s = int(cooldown_s)
        self._approval_status_resolver = approval_status_resolver or _approval_is_pending

    def evaluate(self, *, tenant_id: str, recipient_user_id: str, channel: str, alert_code: str, affected_user_id: str, business_id: str = "", include_record: bool = False):
        dedup_key = build_alert_notification_dedup_key(tenant_id=tenant_id, recipient_user_id=recipient_user_id, channel=channel, alert_code=alert_code, affected_user_id=affected_user_id, business_id=business_id)
        record = self._store_factory.for_tenant(tenant_id=tenant_id).get(dedup_key=dedup_key)
        if record is None:
            decision = AlertSuppressionDecision(should_send=True, reason='first_send')
        elif record.is_pending:
            pending_id = str(record.pending_approval_id)
            active = pending_id.startswith('reservation:') or bool(self._approval_status_resolver(pending_id))
            decision = AlertSuppressionDecision(should_send=not active, reason='approval_pending' if active else 'approval_terminal')
        elif int(now_epoch_s()) - int(record.sent_at_epoch_s) < int(self._cooldown_s):
            decision = AlertSuppressionDecision(should_send=False, reason='cooldown_active')
        else:
            decision = AlertSuppressionDecision(should_send=True, reason='cooldown_elapsed')
        return (dedup_key, decision, record) if include_record else (dedup_key, decision)

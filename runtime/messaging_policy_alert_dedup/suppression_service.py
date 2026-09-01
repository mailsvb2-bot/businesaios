"""Alert notification suppression (cooldown/dedup)."""

from __future__ import annotations

from governance.approval_store import build_default_approval_store
from runtime.messaging_policy_alert_dedup.cooldown_check import is_in_cooldown
from runtime.messaging_policy_alert_dedup.cooldown_seconds import DEFAULT_ALERT_NOTIFICATION_COOLDOWN_S
from runtime.messaging_policy_alert_dedup.dedup_key import build_alert_notification_dedup_key
from runtime.messaging_policy_alert_dedup.suppression_decision import AlertSuppressionDecision
from runtime.messaging_policy_alert_dedup.time_now import now_epoch_s


def _approval_is_pending(approval_id: str, *, approval_store_factory=build_default_approval_store) -> bool:
    try:
        record = approval_store_factory().get(str(approval_id))
    except Exception:
        return True
    if record is None:
        return False
    status = str(getattr(getattr(record, "status", ""), "value", getattr(record, "status", ""))).strip().casefold()
    return status in {"requested", "approved"}


class AlertNotificationSuppressionService:
    def __init__(self, *, store, cooldown_s: int = DEFAULT_ALERT_NOTIFICATION_COOLDOWN_S, approval_status_resolver=None):
        self._store = store
        self._cooldown_s = int(cooldown_s)
        self._approval_status_resolver = approval_status_resolver or _approval_is_pending

    def evaluate(self, *, tenant_id: str, recipient_user_id: str, channel: str, alert_code: str, affected_user_id: str, business_id: str = "") -> tuple[str, AlertSuppressionDecision]:
        dedup_key = build_alert_notification_dedup_key(tenant_id=tenant_id, recipient_user_id=recipient_user_id, channel=channel, alert_code=alert_code, affected_user_id=affected_user_id, business_id=business_id)
        record = self._store.get(dedup_key=dedup_key)
        if record is None:
            return dedup_key, AlertSuppressionDecision(should_send=True, reason="first_send")
        if record.is_pending:
            if bool(self._approval_status_resolver(str(record.pending_approval_id))):
                return dedup_key, AlertSuppressionDecision(should_send=False, reason="approval_pending")
            return dedup_key, AlertSuppressionDecision(should_send=True, reason="approval_terminal")
        current = now_epoch_s()
        if is_in_cooldown(last_sent_epoch_s=int(record.sent_at_epoch_s), now_epoch_s=current, cooldown_s=self._cooldown_s):
            return dedup_key, AlertSuppressionDecision(should_send=False, reason="cooldown_active")
        return dedup_key, AlertSuppressionDecision(should_send=True, reason="cooldown_elapsed")

    decide = evaluate
    issue = evaluate

from __future__ import annotations

from runtime.messaging_policy_alert_dedup.notifier_result import DedupAlertNotifierResult


class DedupingMessagingPolicyAlertNotifier:
    def __init__(self, *, base_notifier, suppression_service, mark_sent_service):
        self._base_notifier = base_notifier
        self._suppression_service = suppression_service
        self._mark_sent_service = mark_sent_service

    def notify(self, *, plan, effects, decision_id: str, correlation_id: str) -> DedupAlertNotifierResult:
        total = sent = suppressed = pending = 0
        for item in tuple(plan.items or ()):
            total += 1
            dedup_key, decision = self._suppression_service.evaluate(tenant_id=item.tenant_id, recipient_user_id=item.recipient_user_id, channel=item.channel, alert_code=item.alert_code, affected_user_id=item.affected_user_id, business_id=str(getattr(item, "business_id", "") or ""))
            if not decision.should_send:
                suppressed += 1
                continue
            result = self._base_notifier.notify(plan=type(plan)(items=(item,)), effects=effects, decision_id=decision_id, correlation_id=correlation_id)
            if int(getattr(result, "notifications_sent", 0)) > 0:
                sent += 1
                self._mark_sent_service.mark_sent(dedup_key=dedup_key)
                continue
            pending_ids = tuple(getattr(result, "pending_approval_ids", ()) or ())
            if pending_ids:
                pending += 1
                self._mark_sent_service.mark_pending(dedup_key=dedup_key, approval_id=str(pending_ids[0]))
        return DedupAlertNotifierResult(notifications_total=total, notifications_sent=sent, notifications_suppressed=suppressed, notifications_pending=pending)

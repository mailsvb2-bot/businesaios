from __future__ import annotations

from dataclasses import replace

from runtime.messaging_policy_alert_dedup.notifier_result import DedupAlertNotifierResult


class TenantAwareDedupingMessagingPolicyAlertNotifier:
    def __init__(self, *, base_notifier, suppression_service, mark_sent_service):
        self._base_notifier, self._suppression_service, self._mark_sent_service = base_notifier, suppression_service, mark_sent_service

    def notify(self, *, plan, effects, decision_id: str, correlation_id: str) -> DedupAlertNotifierResult:
        total = sent = suppressed = pending = 0
        for item in tuple(plan.items or ()):
            total += 1
            dedup_key, decision, expected = self._suppression_service.evaluate(tenant_id=item.tenant_id, recipient_user_id=item.recipient_user_id, channel=item.channel, alert_code=item.alert_code, affected_user_id=item.affected_user_id, business_id=str(getattr(item, 'business_id', '') or ''), include_record=True)
            if not decision.should_send:
                suppressed += 1
                continue
            reservation_id = f"{decision_id}:{correlation_id}:{total}"
            if not self._mark_sent_service.reserve(tenant_id=item.tenant_id, dedup_key=dedup_key, expected_record=expected, reservation_id=reservation_id):
                suppressed += 1
                continue
            bound_item = replace(item, dedup_key=dedup_key, dedup_reservation_id=reservation_id)
            result = self._base_notifier.notify(plan=type(plan)(items=(bound_item,)), effects=effects, decision_id=decision_id, correlation_id=correlation_id)
            if int(getattr(result, 'notifications_sent', 0)) > 0:
                sent += 1
                self._mark_sent_service.mark_sent(tenant_id=item.tenant_id, dedup_key=dedup_key, reservation_id=reservation_id)
                continue
            pending_ids = tuple(getattr(result, 'pending_approval_ids', ()) or ())
            if pending_ids:
                pending += 1
                self._mark_sent_service.mark_pending(tenant_id=item.tenant_id, dedup_key=dedup_key, approval_id=str(pending_ids[0]), reservation_id=reservation_id)
                continue
            if int(getattr(result, 'notifications_ambiguous', 0)) <= 0:
                self._mark_sent_service.release(tenant_id=item.tenant_id, dedup_key=dedup_key, reservation_id=reservation_id)
        return DedupAlertNotifierResult(notifications_total=total, notifications_sent=sent, notifications_suppressed=suppressed, notifications_pending=pending)

from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.notifier_result import AlertNotifierResult


class MessagingPolicyAlertNotifier:
    def notify(self, *, plan, effects, decision_id: str, correlation_id: str) -> AlertNotifierResult:
        sent = total = 0
        pending_ids = []
        for item in tuple(plan.items or ()):
            total += 1
            result = effects.send_message(decision_id=str(decision_id), correlation_id=str(correlation_id), tenant_id=str(item.tenant_id), business_id=str(getattr(item, "business_id", "") or ""), user_id=str(item.recipient_user_id), text=str(item.text), channel=str(item.channel), priority="high", critical=False, reply_markup=None, callback_query_id=None, track_event_type="messaging_policy_alert_sent", track_payload={"tenant_id": item.tenant_id, "alert_code": item.alert_code, "alert_level": item.alert_level, "affected_user_id": item.affected_user_id, "kind": "observability_alert"})
            if isinstance(result, dict) and bool(result.get("ok")):
                sent += 1
                continue
            meta = dict(result.get("meta") or {}) if isinstance(result, dict) else {}
            approval_id = str(meta.get("approval_id") or "").strip()
            if str(meta.get("mode") or "").strip().casefold() == "approval_required" and approval_id:
                pending_ids.append(approval_id)
        return AlertNotifierResult(notifications_total=total, notifications_sent=sent, pending_approval_ids=tuple(pending_ids))

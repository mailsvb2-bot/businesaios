from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.notifier_result import AlertNotifierResult


class MessagingPolicyAlertNotifier:
    def notify(self, *, plan, effects, decision_id: str, correlation_id: str) -> AlertNotifierResult:
        sent = 0
        total = 0
        for item in tuple(plan.items or ()):
            total += 1
            result = effects.send_message(decision_id=str(decision_id), correlation_id=str(correlation_id), user_id=str(item.recipient_user_id), text=str(item.text), channel=str(item.channel), priority="high", critical=False, reply_markup=None, callback_query_id=None, track_event_type="messaging_policy_alert_sent", track_payload={"tenant_id": item.tenant_id, "alert_code": item.alert_code, "alert_level": item.alert_level, "affected_user_id": item.affected_user_id, "kind": "observability_alert"})
            if isinstance(result, dict) and bool(result.get("ok")):
                sent += 1
        return AlertNotifierResult(notifications_total=int(total), notifications_sent=int(sent))

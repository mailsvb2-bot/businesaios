from __future__ import annotations

from runtime.messaging_policy_alert_subscriptions.notifier_result import AlertNotifierResult


class MessagingPolicyAlertNotifier:
    def notify(self, *, plan, effects, decision_id: str, correlation_id: str) -> AlertNotifierResult:
        sent = total = ambiguous = terminal_failed = 0
        pending_ids = []
        for item in tuple(plan.items or ()):
            total += 1
            dedup_context = {"dedup_key": str(getattr(item, "dedup_key", "") or ""), "reservation_id": str(getattr(item, "dedup_reservation_id", "") or "")}
            track_payload = {"tenant_id": item.tenant_id, "alert_code": item.alert_code, "alert_level": item.alert_level, "affected_user_id": item.affected_user_id, "kind": "observability_alert", **({"_alert_dedup": dedup_context} if all(dedup_context.values()) else {})}
            result = effects.send_message(decision_id=str(decision_id), correlation_id=str(correlation_id), tenant_id=str(item.tenant_id), business_id=str(getattr(item, "business_id", "") or ""), user_id=str(item.recipient_user_id), text=str(item.text), channel=str(item.channel), priority="high", critical=False, reply_markup=None, callback_query_id=None, track_event_type="messaging_policy_alert_sent", track_payload=track_payload)
            if isinstance(result, dict) and bool(result.get("ok")):
                sent += 1
                continue
            meta = dict(result.get("meta") or {}) if isinstance(result, dict) else {}
            approval_id = str(meta.get("approval_id") or "").strip()
            mode = str(meta.get("mode") or "").strip().casefold()
            if mode == "approval_required" and approval_id:
                pending_ids.append(approval_id)
            elif mode == "in_progress" or str(meta.get("provider_status") or "") == "ambiguous_delivery":
                ambiguous += 1
            else:
                terminal_failed += 1
        return AlertNotifierResult(notifications_total=total, notifications_sent=sent, pending_approval_ids=tuple(pending_ids), notifications_ambiguous=ambiguous, notifications_terminal_failed=terminal_failed)

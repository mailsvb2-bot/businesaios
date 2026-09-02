from runtime.messaging_policy_alert_dedup.inmemory_store import InMemoryAlertNotificationDedupStore
from runtime.messaging_policy_alert_dedup.mark_sent_service import AlertNotificationMarkSentService
from runtime.messaging_policy_alert_dedup.notifier import DedupingMessagingPolicyAlertNotifier
from runtime.messaging_policy_alert_dedup.suppression_service import AlertNotificationSuppressionService
from runtime.messaging_policy_alert_subscriptions.notification_item import AlertNotificationItem
from runtime.messaging_policy_alert_subscriptions.notification_plan import AlertNotificationPlan


class _BaseNotifier:
    def __init__(self):
        self.calls = []

    def notify(self, *, plan, effects, decision_id: str, correlation_id: str):
        self.calls.append(plan)
        return type("R", (), {"notifications_total": 1, "notifications_sent": 1})()


def test_deduping_notifier_suppresses_second_send(monkeypatch):
    import runtime.messaging_policy_alert_dedup.mark_sent_service as mark_mod
    import runtime.messaging_policy_alert_dedup.suppression_service as sup_mod
    current = {"t": 100}
    monkeypatch.setattr(mark_mod, "now_epoch_s", lambda: current["t"])
    monkeypatch.setattr(sup_mod, "now_epoch_s", lambda: current["t"])
    store = InMemoryAlertNotificationDedupStore()
    notifier = DedupingMessagingPolicyAlertNotifier(base_notifier=_BaseNotifier(), suppression_service=AlertNotificationSuppressionService(store=store, cooldown_s=60), mark_sent_service=AlertNotificationMarkSentService(store=store))
    plan = AlertNotificationPlan(items=(AlertNotificationItem(tenant_id="t1", recipient_user_id="ceo-1", channel="telegram", text="Alert text", alert_code="low_success_rate", alert_level="critical", affected_user_id="user-42"),))
    first = notifier.notify(plan=plan, effects=None, decision_id="d1", correlation_id="c1")
    second = notifier.notify(plan=plan, effects=None, decision_id="d1", correlation_id="c2")
    assert first.notifications_sent == 1
    assert second.notifications_sent == 0
    assert second.notifications_suppressed == 1

class _ApprovalEffects:
    def __init__(self):
        self.calls = 0

    def send_message(self, **kwargs):
        self.calls += 1
        return {"ok": False, "meta": {"mode": "approval_required", "approval_id": "ap-pending"}}


def test_pending_approval_reservation_suppresses_duplicate_until_terminal(monkeypatch):
    from runtime.messaging_policy_alert_subscriptions.notifier import MessagingPolicyAlertNotifier
    import runtime.messaging_policy_alert_dedup.mark_sent_service as mark_mod

    monkeypatch.setattr(mark_mod, "now_epoch_s", lambda: 100)
    approval = {"active": True}
    store = InMemoryAlertNotificationDedupStore()
    mark = AlertNotificationMarkSentService(store=store)
    suppression = AlertNotificationSuppressionService(store=store, cooldown_s=60, approval_status_resolver=lambda _approval_id: approval["active"])
    notifier = DedupingMessagingPolicyAlertNotifier(base_notifier=MessagingPolicyAlertNotifier(), suppression_service=suppression, mark_sent_service=mark)
    effects = _ApprovalEffects()
    plan = AlertNotificationPlan(items=(AlertNotificationItem(tenant_id="t1", business_id="biz-a", recipient_user_id="C1", channel="slack", text="Alert text", alert_code="a1", alert_level="critical", affected_user_id="u1"),))

    first = notifier.notify(plan=plan, effects=effects, decision_id="d1", correlation_id="c1")
    second = notifier.notify(plan=plan, effects=effects, decision_id="d2", correlation_id="c2")
    assert first.notifications_pending == 1 and first.notifications_sent == 0
    assert second.notifications_suppressed == 1 and effects.calls == 1

    approval["active"] = False
    third = notifier.notify(plan=plan, effects=effects, decision_id="d3", correlation_id="c3")
    assert third.notifications_pending == 1 and effects.calls == 2

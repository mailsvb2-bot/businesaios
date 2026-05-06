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

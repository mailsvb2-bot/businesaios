from runtime.messaging_policy_alert_subscriptions.notification_item import AlertNotificationItem
from runtime.messaging_policy_alert_subscriptions.notification_plan import AlertNotificationPlan
from runtime.messaging_policy_alert_subscriptions.notifier import MessagingPolicyAlertNotifier


class _Effects:
    def __init__(self):
        self.items = []

    def send_message(self, **kwargs):
        self.items.append(kwargs)
        return {"ok": True}


def test_notifier_sends_notifications():
    notifier = MessagingPolicyAlertNotifier()
    effects = _Effects()
    plan = AlertNotificationPlan(items=(AlertNotificationItem(tenant_id="t1", recipient_user_id="ceo-1", channel="telegram", text="Alert text", alert_code="low_success_rate", alert_level="critical", affected_user_id="user-42"),))
    out = notifier.notify(plan=plan, effects=effects, decision_id="d1", correlation_id="c1")
    assert out.notifications_total == 1
    assert out.notifications_sent == 1
    assert effects.items[0]["channel"] == "telegram"
    assert effects.items[0]["track_event_type"] == "messaging_policy_alert_sent"

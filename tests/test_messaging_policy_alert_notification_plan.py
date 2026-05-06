from runtime.messaging_policy_alert_subscriptions.match_service import AlertSubscriptionMatchService
from runtime.messaging_policy_alert_subscriptions.notification_planner import AlertNotificationPlanner
from runtime.messaging_policy_alert_subscriptions.subscription_record import AlertSubscriptionRecord
from runtime.messaging_policy_alerts.alert_item import MessagingPolicyAlertItem


def test_notification_planner_builds_items():
    planner = AlertNotificationPlanner()
    match_service = AlertSubscriptionMatchService()
    alerts = (MessagingPolicyAlertItem(code="low_success_rate", level="critical", title="Low success rate", detail="Too low", metric_name="success_rate", metric_value=0.2, threshold_value=0.6),)
    subscriptions = (AlertSubscriptionRecord(tenant_id="t1", recipient_user_id="ceo-1", channel="email", min_level="warn", enabled=True, code_filters=(), user_scope=()),)
    plan = planner.build_plan(tenant_id="t1", affected_user_id="user-1", alerts=alerts, subscriptions=subscriptions, date_from="2026-03-01T00:00:00+00:00", date_to="2026-03-02T00:00:00+00:00", match_service=match_service)
    assert len(plan.items) == 1
    assert plan.items[0].channel == "email"
    assert "low_success_rate" in plan.items[0].text

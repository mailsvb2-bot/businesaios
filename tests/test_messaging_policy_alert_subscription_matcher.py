from runtime.messaging_policy_alert_subscriptions.subscription_matcher import subscription_matches
from runtime.messaging_policy_alert_subscriptions.subscription_record import AlertSubscriptionRecord
from runtime.messaging_policy_alerts.alert_item import MessagingPolicyAlertItem


def test_subscription_matches_by_level_code_and_scope():
    sub = AlertSubscriptionRecord(tenant_id="t1", recipient_user_id="ceo-1", channel="telegram", min_level="warn", enabled=True, code_filters=("low_success_rate",), user_scope=("user-42",))
    alert_item = MessagingPolicyAlertItem(code="low_success_rate", level="critical", title="Low success rate", detail="Too low", metric_name="success_rate", metric_value=0.2, threshold_value=0.6)
    assert subscription_matches(subscription=sub, alert_item=alert_item, affected_user_id="user-42") is True

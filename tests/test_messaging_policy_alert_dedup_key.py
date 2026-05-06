from runtime.messaging_policy_alert_dedup.dedup_key import build_alert_notification_dedup_key


def test_build_alert_notification_dedup_key():
    out = build_alert_notification_dedup_key(tenant_id="t1", recipient_user_id="ceo-1", channel="telegram", alert_code="low_success_rate", affected_user_id="user-42")
    assert out == "t1|ceo-1|telegram|low_success_rate|user-42"

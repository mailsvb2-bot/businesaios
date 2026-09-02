from runtime.messaging_policy_alert_dedup.dedup_key import build_alert_notification_dedup_key


def test_build_alert_notification_dedup_key():
    out = build_alert_notification_dedup_key(tenant_id="t1", recipient_user_id="ceo-1", channel="telegram", alert_code="low_success_rate", affected_user_id="user-42")
    assert out == "t1|ceo-1|telegram|low_success_rate|user-42"


def test_dedup_key_adds_business_scope_without_changing_legacy_shape():
    legacy = build_alert_notification_dedup_key(tenant_id="t1", recipient_user_id="ceo-1", channel="telegram", alert_code="a1", affected_user_id="u1")
    biz_a = build_alert_notification_dedup_key(tenant_id="t1", business_id="biz-a", recipient_user_id="ceo-1", channel="telegram", alert_code="a1", affected_user_id="u1")
    biz_b = build_alert_notification_dedup_key(tenant_id="t1", business_id="biz-b", recipient_user_id="ceo-1", channel="telegram", alert_code="a1", affected_user_id="u1")
    assert legacy == "t1|ceo-1|telegram|a1|u1"
    assert biz_a == "t1|biz-a|ceo-1|telegram|a1|u1"
    assert biz_a != biz_b

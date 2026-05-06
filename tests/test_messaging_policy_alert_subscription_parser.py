from runtime.messaging_policy_alert_subscriptions.subscription_parser import parse_subscription


def test_parse_subscription_builds_record():
    out = parse_subscription({"recipient_user_id": "ceo-1", "channel": "email", "min_level": "critical", "enabled": True, "code_filters": ["low_success_rate"], "user_scope": ["user-42"]}, tenant_id="t1")
    assert out is not None
    assert out.tenant_id == "t1"
    assert out.channel == "email"
    assert out.min_level == "critical"

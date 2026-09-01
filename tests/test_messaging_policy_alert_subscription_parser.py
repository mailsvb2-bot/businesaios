from runtime.messaging_policy_alert_subscriptions.subscription_parser import parse_subscription


def test_parse_subscription_builds_record():
    out = parse_subscription({"recipient_user_id": "ceo-1", "channel": "email", "min_level": "critical", "business_id": "business-a", "enabled": True, "code_filters": ["low_success_rate"], "user_scope": ["user-42"]}, tenant_id="t1")
    assert out is not None
    assert out.tenant_id == "t1"
    assert out.channel == "email"
    assert out.min_level == "critical"


def test_parse_subscription_preserves_explicit_business_scope_without_tenant_inference():
    scoped = parse_subscription({"recipient_user_id": "C123", "channel": "slack", "business_id": "business-a"}, tenant_id="tenant-a")
    legacy = parse_subscription({"recipient_user_id": "C123", "channel": "slack"}, tenant_id="tenant-a")
    assert scoped is not None and scoped.business_id == "business-a"
    assert legacy is not None and legacy.business_id == ""

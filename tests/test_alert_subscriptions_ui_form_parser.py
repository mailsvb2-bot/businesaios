import pytest

from interfaces.web.settings.alert_subscriptions.form_parser import parse_alert_subscriptions_form


def test_parse_alert_subscriptions_form():
    out = parse_alert_subscriptions_form(
        {
            "items": [
                {
                    "recipient_user_id": "ceo-1",
                    "channel": "email",
                    "min_level": "critical",
                    "business_id": "business-a",
                    "enabled": True,
                    "code_filters": ["low_success_rate"],
                    "user_scope": ["user-42"],
                }
            ]
        }
    )
    assert len(out) == 1
    assert out[0]["channel"] == "email"
    assert out[0]["min_level"] == "critical"
    assert out[0]["business_id"] == "business-a"


def test_native_alert_subscription_requires_business_scope():
    for channel in ("slack", "discord", "instagram", "messenger", "line", "viber"):
        with pytest.raises(ValueError, match="business_id is required"):
            parse_alert_subscriptions_form({"items": [{"recipient_user_id": "C123", "channel": channel, "business_id": ""}]})

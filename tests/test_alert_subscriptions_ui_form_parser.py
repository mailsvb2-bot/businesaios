from interfaces.web.settings.alert_subscriptions.form_parser import parse_alert_subscriptions_form


def test_parse_alert_subscriptions_form():
    out = parse_alert_subscriptions_form(
        {
            "items": [
                {
                    "recipient_user_id": "ceo-1",
                    "channel": "email",
                    "min_level": "critical",
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

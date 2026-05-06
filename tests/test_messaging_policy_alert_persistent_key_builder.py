from runtime.messaging_policy_alert_dedup_persistent.settings_key_builder import build_settings_key


def test_build_settings_key():
    out = build_settings_key(dedup_key="t1|ceo|telegram|low_success_rate|u1")
    assert out == "messaging_policy:alert_dedup:t1|ceo|telegram|low_success_rate|u1"

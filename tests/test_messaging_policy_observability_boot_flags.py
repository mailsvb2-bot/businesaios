from runtime.boot.web.observability_boot_plan import MessagingPolicyObservabilityBootFlags


def test_flags_default_to_all_enabled():
    flags = MessagingPolicyObservabilityBootFlags()
    assert flags.navigation is True
    assert flags.snapshot is True
    assert flags.traces is True
    assert flags.dashboard is True
    assert flags.alerts is True
    assert flags.alert_subscriptions is True
    assert flags.messaging_preferences is True

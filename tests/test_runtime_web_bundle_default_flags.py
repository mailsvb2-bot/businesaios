from runtime.boot.web.runtime_web_default_flags import build_runtime_web_default_flags
from runtime.boot.web.runtime_web_services import RuntimeWebServices


class _ReadService:
    pass


def test_default_flags_follow_available_services():
    flags = build_runtime_web_default_flags(
        services=RuntimeWebServices(
            project_root='.',
            settings_gateway=object(),
            messaging_policy_read_service=_ReadService(),
            messaging_policy_event_store=object(),
        )
    )
    assert flags.navigation is True
    assert flags.snapshot is True
    assert flags.traces is True
    assert flags.dashboard is True
    assert flags.alerts is True
    assert flags.alert_subscriptions is True
    assert flags.messaging_preferences is True


def test_default_flags_fail_closed_for_missing_dependencies():
    flags = build_runtime_web_default_flags(
        services=RuntimeWebServices(project_root='.', settings_gateway=None, messaging_policy_read_service=None, messaging_policy_event_store=None)
    )
    assert flags.navigation is True
    assert flags.snapshot is False
    assert flags.traces is False
    assert flags.dashboard is False
    assert flags.alerts is False
    assert flags.alert_subscriptions is False
    assert flags.messaging_preferences is False

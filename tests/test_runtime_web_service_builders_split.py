from pathlib import Path

from runtime.boot.web.runtime_web_service_builders import build_runtime_web_routed_services


class _Marker:
    pass


def test_runtime_web_service_builders_delegate_to_owned_parts(monkeypatch):
    calls = []

    class Nav:
        messaging_policy_observability_nav_bundle = 'nav'

    class Settings:
        messaging_preferences_bundle = 'prefs'
        alert_subscriptions_bundle = 'alerts-ui'

    class Snapshot:
        messaging_policy_snapshot_bundle = 'snap'

    class Events:
        messaging_policy_trace_search_bundle = 'trace-bundle'
        messaging_policy_dashboard_bundle = 'dash-bundle'
        messaging_policy_alerts_bundle = 'alerts-bundle'
        messaging_policy_trace_search_service = 'trace-service'
        messaging_policy_dashboard_service = 'dash-service'
        messaging_policy_alert_service = 'alert-service'
        messaging_policy_alert_subscription_service = 'sub-service'
        messaging_policy_alert_notifier_stack = 'notifier'

    monkeypatch.setattr(
        'runtime.boot.web.runtime_web_service_builders.build_runtime_web_navigation_parts',
        lambda: calls.append('nav') or Nav(),
    )
    monkeypatch.setattr(
        'runtime.boot.web.runtime_web_service_builders.build_runtime_web_settings_parts',
        lambda *, args: calls.append(('settings', args.project_root.name)) or Settings(),
    )
    monkeypatch.setattr(
        'runtime.boot.web.runtime_web_service_builders.build_runtime_web_snapshot_parts',
        lambda *, args: calls.append(('snapshot', args.project_root.name)) or Snapshot(),
    )
    monkeypatch.setattr(
        'runtime.boot.web.runtime_web_service_builders.build_runtime_web_event_parts',
        lambda *, args: calls.append(('events', args.project_root.name)) or Events(),
    )

    out = build_runtime_web_routed_services(project_root=Path('/tmp/demo'), settings_gateway=_Marker())
    assert out.messaging_policy_observability_nav_bundle == 'nav'
    assert out.messaging_preferences_bundle == 'prefs'
    assert out.messaging_policy_alert_notifier_stack == 'notifier'
    assert calls[0] == 'nav'
    assert ('settings', 'demo') in calls
    assert ('snapshot', 'demo') in calls
    assert ('events', 'demo') in calls

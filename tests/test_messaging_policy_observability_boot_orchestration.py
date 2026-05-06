from pathlib import Path

from runtime.boot.web.boot_observability import boot_messaging_policy_observability_fastapi
from runtime.boot.web.observability_boot_plan import MessagingPolicyObservabilityBootFlags


class DummyApp:
    pass


def test_boot_orchestration_skips_disabled_and_missing_dependencies(monkeypatch):
    calls = []

    monkeypatch.setattr('runtime.boot.web.boot_observability.boot_navigation', lambda *, app: calls.append('navigation'))
    monkeypatch.setattr('runtime.boot.web.boot_observability.boot_snapshot', lambda *, app, read_service: calls.append('snapshot'))
    monkeypatch.setattr('runtime.boot.web.boot_observability.boot_traces', lambda *, app, event_store: calls.append('traces'))
    monkeypatch.setattr('runtime.boot.web.boot_observability.boot_dashboard', lambda *, app, event_store: calls.append('dashboard'))
    monkeypatch.setattr('runtime.boot.web.boot_observability.boot_alerts', lambda *, app, event_store: calls.append('alerts'))
    monkeypatch.setattr('runtime.boot.web.boot_observability.boot_alert_subscriptions', lambda *, app, project_root, settings_gateway: calls.append('alert_subscriptions'))
    monkeypatch.setattr('runtime.boot.web.boot_observability.boot_messaging_preferences', lambda *, app, project_root, settings_gateway: calls.append('messaging_preferences'))

    out = boot_messaging_policy_observability_fastapi(
        app=DummyApp(),
        project_root=Path('.'),
        settings_gateway=None,
        messaging_policy_event_store=None,
        messaging_policy_read_service=object(),
        flags=MessagingPolicyObservabilityBootFlags(alerts=False),
    )

    assert calls == ['navigation', 'snapshot']
    assert out.booted_keys == ('navigation', 'snapshot')

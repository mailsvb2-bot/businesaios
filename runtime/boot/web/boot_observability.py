from __future__ import annotations

from runtime.boot.web.fastapi_components import boot_alert_subscriptions as boot_alert_subscriptions_fastapi
from runtime.boot.web.fastapi_components import boot_alerts as boot_alerts_fastapi
from runtime.boot.web.fastapi_components import boot_dashboard as boot_dashboard_fastapi
from runtime.boot.web.fastapi_components import boot_messaging_preferences as boot_messaging_preferences_fastapi
from runtime.boot.web.fastapi_components import boot_navigation as boot_navigation_fastapi
from runtime.boot.web.fastapi_components import boot_snapshot as boot_snapshot_fastapi
from runtime.boot.web.fastapi_components import boot_traces as boot_traces_fastapi
from runtime.boot.web.flask_components import boot_alert_subscriptions as boot_alert_subscriptions_flask
from runtime.boot.web.flask_components import boot_alerts as boot_alerts_flask
from runtime.boot.web.flask_components import boot_dashboard as boot_dashboard_flask
from runtime.boot.web.flask_components import boot_messaging_preferences as boot_messaging_preferences_flask
from runtime.boot.web.flask_components import boot_navigation as boot_navigation_flask
from runtime.boot.web.flask_components import boot_snapshot as boot_snapshot_flask
from runtime.boot.web.flask_components import boot_traces as boot_traces_flask
from runtime.boot.web.observability_boot_plan import (
    MessagingPolicyObservabilityBootFlags,
    MessagingPolicyObservabilityBootResult,
    ObservabilityBootArgs,
    execute_observability_boot_plan,
)

CANON_BOOT_WIRING_ONLY = True

def boot_messaging_policy_observability_fastapi(
    *,
    app,
    project_root,
    settings_gateway,
    messaging_policy_event_store,
    messaging_policy_read_service,
    flags=None,
):
    args = ObservabilityBootArgs(
        app=app,
        project_root=project_root,
        settings_gateway=settings_gateway,
        messaging_policy_event_store=messaging_policy_event_store,
        messaging_policy_read_service=messaging_policy_read_service,
    )
    return execute_observability_boot_plan(
        args=args,
        flags=flags,
        boot_navigation=boot_navigation,
        boot_snapshot=boot_snapshot,
        boot_traces=boot_traces,
        boot_dashboard=boot_dashboard,
        boot_alerts=boot_alerts,
        boot_alert_subscriptions=boot_alert_subscriptions,
        boot_messaging_preferences=boot_messaging_preferences,
    )


def boot_messaging_policy_observability_flask(
    *,
    app,
    project_root,
    settings_gateway,
    messaging_policy_event_store,
    messaging_policy_read_service,
    flags=None,
):
    args = ObservabilityBootArgs(
        app=app,
        project_root=project_root,
        settings_gateway=settings_gateway,
        messaging_policy_event_store=messaging_policy_event_store,
        messaging_policy_read_service=messaging_policy_read_service,
    )
    return execute_observability_boot_plan(
        args=args,
        flags=flags,
        boot_navigation=boot_navigation_flask,
        boot_snapshot=boot_snapshot_flask,
        boot_traces=boot_traces_flask,
        boot_dashboard=boot_dashboard_flask,
        boot_alerts=boot_alerts_flask,
        boot_alert_subscriptions=boot_alert_subscriptions_flask,
        boot_messaging_preferences=boot_messaging_preferences_flask,
    )

# Canonical default component aliases for orchestration tests and lightweight internal callers.
boot_navigation = boot_navigation_fastapi
boot_snapshot = boot_snapshot_fastapi
boot_traces = boot_traces_fastapi
boot_dashboard = boot_dashboard_fastapi
boot_alerts = boot_alerts_fastapi
boot_alert_subscriptions = boot_alert_subscriptions_fastapi
boot_messaging_preferences = boot_messaging_preferences_fastapi

__all__ = [
    'boot_messaging_policy_observability_fastapi',
    'boot_messaging_policy_observability_flask',
    'MessagingPolicyObservabilityBootFlags',
    'MessagingPolicyObservabilityBootResult',
]

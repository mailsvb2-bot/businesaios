from __future__ import annotations

from interfaces.web.debug.messaging_policy_alerts.fastapi_adapter import (
    register_fastapi_routes as _register_alert_routes,
)
from interfaces.web.debug.messaging_policy_dashboard.fastapi_adapter import (
    register_fastapi_routes as _register_dashboard_routes,
)
from interfaces.web.debug.messaging_policy_observability_nav.fastapi_adapter import (
    register_fastapi_routes as _register_nav_routes,
)
from interfaces.web.debug.messaging_policy_snapshot.fastapi_adapter import (
    register_fastapi_routes as _register_snapshot_routes,
)
from interfaces.web.debug.messaging_policy_trace_search.fastapi_adapter import (
    register_fastapi_routes as _register_trace_routes,
)
from interfaces.web.settings.alert_subscriptions_integration.fastapi_adapter import (
    register_fastapi_routes as _register_alert_subscriptions_routes,
)
from interfaces.web.settings.messaging_preferences_integration.fastapi_adapter import (
    register_fastapi_routes as _register_preferences_routes,
)
from runtime.boot.web.framework_boot import boot_with_bundle
from runtime.boot.web.messaging_policy_service_graph import build_messaging_policy_service_graph
from runtime.boot.web.runtime_web_service_builders import (
    build_alert_subscriptions_bundle,
    build_messaging_policy_alerts_bundle,
    build_messaging_policy_dashboard_bundle,
    build_messaging_policy_observability_nav_bundle,
    build_messaging_policy_snapshot_bundle,
    build_messaging_policy_trace_search_bundle,
    build_messaging_preferences_bundle,
)

_PUBLIC_API_MODULE = False
CANON_FASTAPI_COMPONENTS_COLLAPSED_OWNER = True
CANON_BOOT_WIRING_ONLY = True

def boot_alert_subscriptions(*, app, project_root, settings_gateway) -> None:
    boot_with_bundle(
        app=app,
        bundle_builder=build_alert_subscriptions_bundle,
        route_registrar=_register_alert_subscriptions_routes,
        project_root=project_root,
        settings_gateway=settings_gateway,
    )


def boot_alerts(*, app, event_store) -> None:
    graph = build_messaging_policy_service_graph(event_store=event_store)
    boot_with_bundle(
        app=app,
        bundle_builder=build_messaging_policy_alerts_bundle,
        route_registrar=_register_alert_routes,
        dashboard_service=graph.dashboard_service,
    )


def boot_dashboard(*, app, event_store) -> None:
    graph = build_messaging_policy_service_graph(event_store=event_store)
    bundle = build_messaging_policy_dashboard_bundle(trace_search_service=graph.trace_search_service)
    _register_dashboard_routes(app=app, bundle=bundle)


def boot_messaging_preferences(*, app, project_root, settings_gateway) -> None:
    boot_with_bundle(
        app=app,
        bundle_builder=build_messaging_preferences_bundle,
        route_registrar=_register_preferences_routes,
        project_root=project_root,
        settings_gateway=settings_gateway,
    )


def boot_navigation(*, app) -> None:
    boot_with_bundle(
        app=app,
        bundle_builder=build_messaging_policy_observability_nav_bundle,
        route_registrar=_register_nav_routes,
    )


def boot_snapshot(*, app, read_service) -> None:
    boot_with_bundle(
        app=app,
        bundle_builder=build_messaging_policy_snapshot_bundle,
        route_registrar=_register_snapshot_routes,
        read_service=read_service,
    )


def boot_traces(*, app, event_store) -> None:
    boot_with_bundle(
        app=app,
        bundle_builder=build_messaging_policy_trace_search_bundle,
        route_registrar=_register_trace_routes,
        event_store=event_store,
    )


boot_alert_subscriptions_fastapi = boot_alert_subscriptions
boot_messaging_policy_alerts_fastapi = boot_alerts
boot_messaging_policy_dashboard_fastapi = boot_dashboard
boot_messaging_preferences_fastapi = boot_messaging_preferences
boot_messaging_policy_observability_nav_fastapi = boot_navigation
boot_messaging_policy_snapshot_fastapi = boot_snapshot
boot_messaging_policy_trace_search_fastapi = boot_traces


__all__ = [
    "boot_alert_subscriptions",
    "boot_alert_subscriptions_fastapi",
    "boot_alerts",
    "boot_dashboard",
    "boot_messaging_policy_alerts_fastapi",
    "boot_messaging_policy_dashboard_fastapi",
    "boot_messaging_policy_observability_nav_fastapi",
    "boot_messaging_preferences",
    "boot_messaging_policy_snapshot_fastapi",
    "boot_messaging_policy_trace_search_fastapi",
    "boot_messaging_preferences_fastapi",
    "boot_navigation",
    "boot_snapshot",
    "boot_traces",
]

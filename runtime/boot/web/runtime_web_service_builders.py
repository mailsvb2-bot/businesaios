from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from dataclasses import dataclass
from pathlib import Path

from runtime.boot.web.messaging_policy_alert_subscription_service import (
    build_messaging_policy_alert_subscription_service,
)
from runtime.boot.web.messaging_policy_service_graph import build_messaging_policy_service_graph
from runtime.boot.web.runtime_web_build_args import RuntimeWebBuildArgs
from runtime.boot.web.runtime_web_route_bundle_builders import (
    build_alert_subscriptions_bundle,
    build_messaging_policy_alerts_bundle,
    build_messaging_policy_dashboard_bundle,
    build_messaging_policy_observability_nav_bundle,
    build_messaging_policy_snapshot_bundle,
    build_messaging_policy_trace_search_bundle,
    build_messaging_preferences_bundle,
)
from runtime.boot.web.runtime_web_routed_services import RuntimeWebRoutedServices


@dataclass(frozen=True)
class RuntimeWebNavigationParts:
    messaging_policy_observability_nav_bundle: object | None = None


@dataclass(frozen=True)
class RuntimeWebSettingsParts:
    messaging_preferences_bundle: object | None = None
    alert_subscriptions_bundle: object | None = None


@dataclass(frozen=True)
class RuntimeWebSnapshotParts:
    messaging_policy_snapshot_bundle: object | None = None


@dataclass(frozen=True)
class RuntimeWebEventParts:
    messaging_policy_trace_search_bundle: object | None = None
    messaging_policy_dashboard_bundle: object | None = None
    messaging_policy_alerts_bundle: object | None = None
    messaging_policy_trace_search_service: object | None = None
    messaging_policy_dashboard_service: object | None = None
    messaging_policy_alert_service: object | None = None
    messaging_policy_alert_subscription_service: object | None = None
    messaging_policy_alert_notifier_stack: object | None = None


def build_runtime_web_navigation_parts() -> RuntimeWebNavigationParts:
    return RuntimeWebNavigationParts(
        messaging_policy_observability_nav_bundle=build_messaging_policy_observability_nav_bundle(),
    )


def build_runtime_web_settings_parts(*, args) -> RuntimeWebSettingsParts:
    if args.settings_gateway is None:
        return RuntimeWebSettingsParts()
    return RuntimeWebSettingsParts(
        messaging_preferences_bundle=build_messaging_preferences_bundle(
            project_root=args.project_root,
            settings_gateway=args.settings_gateway,
        ),
        alert_subscriptions_bundle=build_alert_subscriptions_bundle(
            project_root=args.project_root,
            settings_gateway=args.settings_gateway,
        ),
    )


def build_runtime_web_snapshot_parts(*, args) -> RuntimeWebSnapshotParts:
    if args.messaging_policy_read_service is None:
        return RuntimeWebSnapshotParts()
    return RuntimeWebSnapshotParts(
        messaging_policy_snapshot_bundle=build_messaging_policy_snapshot_bundle(
            read_service=args.messaging_policy_read_service,
        )
    )


def build_runtime_web_event_parts(*, args) -> RuntimeWebEventParts:
    if args.messaging_policy_event_store is None:
        return RuntimeWebEventParts()

    graph = build_messaging_policy_service_graph(
        event_store=args.messaging_policy_event_store,
    )
    built = build_messaging_policy_alert_subscription_service(
        alert_service=graph.alert_service,
        settings_gateway=args.settings_gateway,
    )
    return RuntimeWebEventParts(
        messaging_policy_trace_search_bundle=build_messaging_policy_trace_search_bundle(
            trace_search_service=graph.trace_search_service,
        ),
        messaging_policy_dashboard_bundle=build_messaging_policy_dashboard_bundle(
            trace_search_service=graph.trace_search_service,
        ),
        messaging_policy_alerts_bundle=build_messaging_policy_alerts_bundle(
            dashboard_service=graph.dashboard_service,
        ),
        messaging_policy_trace_search_service=graph.trace_search_service,
        messaging_policy_dashboard_service=graph.dashboard_service,
        messaging_policy_alert_service=graph.alert_service,
        messaging_policy_alert_subscription_service=built["service"],
        messaging_policy_alert_notifier_stack=built["notifier_stack"],
    )


def build_runtime_web_routed_services(*, project_root, settings_gateway=None, messaging_policy_read_service=None, messaging_policy_event_store=None):
    args = RuntimeWebBuildArgs(
        project_root=Path(project_root),
        settings_gateway=settings_gateway,
        messaging_policy_read_service=messaging_policy_read_service,
        messaging_policy_event_store=messaging_policy_event_store,
    )
    navigation = build_runtime_web_navigation_parts()
    settings = build_runtime_web_settings_parts(args=args)
    snapshot = build_runtime_web_snapshot_parts(args=args)
    events = build_runtime_web_event_parts(args=args)

    return RuntimeWebRoutedServices(
        messaging_preferences_bundle=settings.messaging_preferences_bundle,
        alert_subscriptions_bundle=settings.alert_subscriptions_bundle,
        messaging_policy_snapshot_bundle=snapshot.messaging_policy_snapshot_bundle,
        messaging_policy_trace_search_bundle=events.messaging_policy_trace_search_bundle,
        messaging_policy_dashboard_bundle=events.messaging_policy_dashboard_bundle,
        messaging_policy_alerts_bundle=events.messaging_policy_alerts_bundle,
        messaging_policy_observability_nav_bundle=navigation.messaging_policy_observability_nav_bundle,
        messaging_policy_trace_search_service=events.messaging_policy_trace_search_service,
        messaging_policy_dashboard_service=events.messaging_policy_dashboard_service,
        messaging_policy_alert_service=events.messaging_policy_alert_service,
        messaging_policy_alert_subscription_service=events.messaging_policy_alert_subscription_service,
        messaging_policy_alert_notifier_stack=events.messaging_policy_alert_notifier_stack,
    )

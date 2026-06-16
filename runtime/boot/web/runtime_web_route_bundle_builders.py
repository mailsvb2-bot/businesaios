from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from pathlib import Path

from interfaces.web.debug.messaging_policy_alerts.route_bundle import MessagingPolicyAlertsRouteBundle
from interfaces.web.debug.messaging_policy_dashboard.route_bundle import MessagingPolicyDashboardRouteBundle
from interfaces.web.debug.messaging_policy_observability_nav.route_bundle import (
    MessagingPolicyObservabilityNavRouteBundle,
)
from interfaces.web.debug.messaging_policy_snapshot.route_bundle import MessagingPolicySnapshotRouteBundle
from interfaces.web.debug.messaging_policy_trace_search.route_bundle import MessagingPolicyTraceSearchRouteBundle
from interfaces.web.settings.alert_subscriptions_integration.route_bundle import AlertSubscriptionsRouteBundle
from interfaces.web.settings.messaging_preferences_integration.route_bundle import MessagingPreferencesRouteBundle
from runtime.messaging_policy_alerts.service import MessagingPolicyAlertService
from runtime.messaging_policy_dashboard.service import MessagingPolicyDashboardService
from runtime.messaging_policy_trace.search_service import MessagingPolicyTraceSearchService


class _MessagingPolicyAlertsRouteBundle(MessagingPolicyAlertsRouteBundle):
    def __init__(self, *, alert_service):
        super().__init__(alert_service=alert_service)
        self.alert_service = alert_service


class _MessagingPolicyDashboardRouteBundle(MessagingPolicyDashboardRouteBundle):
    def __init__(self, *, dashboard_service):
        super().__init__(dashboard_service=dashboard_service)
        self.dashboard_service = dashboard_service
        self._dashboard_service = dashboard_service


class _MessagingPolicyTraceSearchRouteBundle(MessagingPolicyTraceSearchRouteBundle):
    def __init__(self, *, search_service):
        super().__init__(search_service=search_service)
        self.search_service = search_service
        self._trace_search_service = search_service


def build_alert_subscriptions_bundle(*, project_root: Path, settings_gateway):
    return AlertSubscriptionsRouteBundle(project_root=project_root, settings_gateway=settings_gateway)


def build_messaging_preferences_bundle(*, project_root: Path, settings_gateway):
    return MessagingPreferencesRouteBundle(project_root=project_root, settings_gateway=settings_gateway)


def build_messaging_policy_observability_nav_bundle():
    return MessagingPolicyObservabilityNavRouteBundle()


def build_messaging_policy_snapshot_bundle(*, read_service):
    return MessagingPolicySnapshotRouteBundle(read_service=read_service)


def build_messaging_policy_trace_search_bundle(*, trace_search_service: MessagingPolicyTraceSearchService):
    return _MessagingPolicyTraceSearchRouteBundle(search_service=trace_search_service)


def build_messaging_policy_dashboard_bundle(*, trace_search_service: MessagingPolicyTraceSearchService):
    dashboard_service = MessagingPolicyDashboardService(trace_search_service=trace_search_service)
    return _MessagingPolicyDashboardRouteBundle(dashboard_service=dashboard_service)


def build_messaging_policy_alerts_bundle(*, dashboard_service: MessagingPolicyDashboardService):
    return _MessagingPolicyAlertsRouteBundle(alert_service=MessagingPolicyAlertService(dashboard_service=dashboard_service))

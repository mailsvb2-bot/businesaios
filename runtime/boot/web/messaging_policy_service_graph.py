from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from dataclasses import dataclass

from runtime.boot.web.messaging_policy_trace_search_service_builder import build_messaging_policy_trace_search_service
from runtime.messaging_policy_alerts.service import MessagingPolicyAlertService
from runtime.messaging_policy_dashboard.service import MessagingPolicyDashboardService
from runtime.messaging_policy_trace.search_service import MessagingPolicyTraceSearchService


@dataclass(frozen=True)
class MessagingPolicyServiceGraph:
    trace_search_service: MessagingPolicyTraceSearchService
    dashboard_service: MessagingPolicyDashboardService
    alert_service: MessagingPolicyAlertService


def build_messaging_policy_dashboard_service(*, trace_search_service) -> MessagingPolicyDashboardService:
    return MessagingPolicyDashboardService(
        trace_search_service=trace_search_service,
    )


def build_messaging_policy_alert_service(*, dashboard_service) -> MessagingPolicyAlertService:
    return MessagingPolicyAlertService(
        dashboard_service=dashboard_service,
    )


def build_messaging_policy_service_graph(*, event_store) -> MessagingPolicyServiceGraph:
    trace_search_service = build_messaging_policy_trace_search_service(
        event_store=event_store,
    )
    dashboard_service = build_messaging_policy_dashboard_service(
        trace_search_service=trace_search_service,
    )
    alert_service = build_messaging_policy_alert_service(
        dashboard_service=dashboard_service,
    )
    return MessagingPolicyServiceGraph(
        trace_search_service=trace_search_service,
        dashboard_service=dashboard_service,
        alert_service=alert_service,
    )


__all__ = [
    "MessagingPolicyServiceGraph",
    "build_messaging_policy_trace_search_service",
    "build_messaging_policy_dashboard_service",
    "build_messaging_policy_alert_service",
    "build_messaging_policy_service_graph",
]

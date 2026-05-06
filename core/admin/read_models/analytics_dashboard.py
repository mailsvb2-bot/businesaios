from __future__ import annotations

from typing import Any

from application.analytics.dashboard_service import ApplicationAnalyticsDashboardService

CANON_ADMIN_ANALYTICS_DASHBOARD = True


def build_admin_analytics_dashboard(event_store: Any, *, tenant_id: str = 'default', window_days: int = 30) -> dict:
    return ApplicationAnalyticsDashboardService(event_store=event_store).build_dashboard_bundle(tenant_id=str(tenant_id), window_days=int(window_days))

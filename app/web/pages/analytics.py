from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.web.components.analytics_dashboard_card import AnalyticsDashboardCard
from app.web.components.analytics_explainability_card import AnalyticsExplainabilityCard
from app.web.components.analytics_rollup_card import AnalyticsRollupCard
from application.analytics.dashboard_service import ApplicationAnalyticsDashboardService
from core.tenancy.normalization import require_tenant_id
from shared.kinded_payloads import build_kinded_payload

CANON_WEB_ANALYTICS_PAGE = True


@dataclass(frozen=True, slots=True)
class AnalyticsPage:
    dashboard_card: AnalyticsDashboardCard = field(default_factory=AnalyticsDashboardCard)
    explainability_card: AnalyticsExplainabilityCard = field(default_factory=AnalyticsExplainabilityCard)
    rollup_card: AnalyticsRollupCard = field(default_factory=AnalyticsRollupCard)

    def build(self, *, event_store: Any, tenant_id: str, window_days: int = 30) -> dict[str, Any]:
        tid = require_tenant_id(tenant_id)
        bundle = ApplicationAnalyticsDashboardService(event_store=event_store).build_dashboard_bundle(tenant_id=tid, window_days=int(window_days))
        return build_kinded_payload('analytics_page', {'tenant_id': tid, 'dashboard': self.dashboard_card.build(bundle['dashboard']), 'explainability': self.explainability_card.build(bundle['explainability']), 'tenant_rollup': self.rollup_card.build(bundle['tenant_rollup'])})

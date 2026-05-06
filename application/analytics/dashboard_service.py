from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from application.analytics.business_analytics_service import ApplicationBusinessAnalyticsService
from core.analytics.analytics_dashboard import AnalyticsDashboardService
from core.analytics.analytics_explainability_trace import AnalyticsExplainabilityService
from core.analytics.analytics_rollup import AnalyticsRollupService


@dataclass
class ApplicationAnalyticsDashboardService:
    event_store: Any
    _business: ApplicationBusinessAnalyticsService = field(init=False)
    _dashboard: AnalyticsDashboardService = field(default_factory=AnalyticsDashboardService)
    _explain: AnalyticsExplainabilityService = field(default_factory=AnalyticsExplainabilityService)
    _rollup: AnalyticsRollupService = field(default_factory=AnalyticsRollupService)

    def __post_init__(self) -> None:
        object.__setattr__(self, '_business', ApplicationBusinessAnalyticsService(event_store=self.event_store))

    def build_dashboard_bundle(self, *, tenant_id: str, window_days: int = 30) -> dict[str, Any]:
        business = self._business.build_scorecard(tenant_id=str(tenant_id), window_days=int(window_days))
        dashboard = self._dashboard.build_dashboard(tenant_id=str(tenant_id), window_days=int(window_days), business_scorecard=business)
        explainability = self._explain.build_from_business_scorecard(scorecard=business)
        tenant_rollup = self._rollup.build_tenant_rollup(dashboard=dashboard, business_scorecard=business)
        return {
            'dashboard': asdict(dashboard),
            'explainability': asdict(explainability),
            'tenant_rollup': asdict(tenant_rollup),
            'business': asdict(business),
        }

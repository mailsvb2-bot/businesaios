from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from application.analytics.dashboard_service import ApplicationAnalyticsDashboardService
from core.analytics.analytics_rollup import AnalyticsRollupService


@dataclass
class FleetAnalyticsCoordinator:
    event_store_factory: Any
    _rollup: AnalyticsRollupService = field(default_factory=AnalyticsRollupService)

    def build_fleet_rollup(self, *, tenant_ids: Iterable[str], window_days: int = 30) -> dict:
        tenant_rollups = []
        for tenant_id in tenant_ids:
            event_store = self.event_store_factory(str(tenant_id))
            bundle = ApplicationAnalyticsDashboardService(event_store=event_store).build_dashboard_bundle(
                tenant_id=str(tenant_id),
                window_days=int(window_days),
            )
            tenant_rollups.append(self._rollup.build_tenant_rollup_from_bundle(bundle=bundle))
        fleet = self._rollup.build_fleet_rollup(tenant_rollups=tenant_rollups)
        return fleet.__dict__.copy()

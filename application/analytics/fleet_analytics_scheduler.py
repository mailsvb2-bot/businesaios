from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from application.analytics.analytics_delivery_service import AnalyticsDeliveryService
from application.analytics.fleet_analytics_coordinator import FleetAnalyticsCoordinator
from application.analytics.persistent_distributed_analytics_materializer import (
    PersistentDistributedAnalyticsMaterializer,
)


@dataclass
class FleetAnalyticsScheduler:
    distributed_materializer: PersistentDistributedAnalyticsMaterializer
    coordinator: FleetAnalyticsCoordinator
    delivery_service: AnalyticsDeliveryService | None = None

    def run_once(self, *, tenant_ids: Iterable[str], window_days: int = 30, export_root: str | None = None) -> dict:
        completed: list[dict] = []
        tenant_list = [str(t) for t in tenant_ids]
        for tenant_id in tenant_list:
            result = self.distributed_materializer.materialize_for_tenant(tenant_id=tenant_id, window_days=int(window_days), export_path=None if export_root is None else f"{export_root}/{tenant_id}.json")
            completed.append(result)
            if self.delivery_service is not None:
                alerts = result.get("alerts", {}).get("alerts", [])
                if alerts:
                    self.delivery_service.deliver_alert_batch(tenant_id=tenant_id, channel="file_drop", alerts=alerts)
        fleet_rollup = self.coordinator.build_fleet_rollup(tenant_ids=tenant_list, window_days=int(window_days))
        return {"completed_count": len(completed), "fleet_rollup": fleet_rollup, "tenants": completed}

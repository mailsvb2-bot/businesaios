from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.analytics.analytics_materializer import AnalyticsMaterializer
from application.analytics.analytics_snapshot_service import AnalyticsSnapshotService
from application.analytics.fleet_queue_job_bridge import AnalyticsFleetQueueJobBridge
from entrypoints.api.analytics_models import AnalyticsMaterializeRequest, AnalyticsQueueMaterializeRequest
from observability.analytics_snapshot_store import SqliteAnalyticsSnapshotStore

CANON_API_ANALYTICS_OPS_ROUTE_HANDLERS = True
CANON_API_ANALYTICS_OPS_ROUTE_HANDLERS_FINAL_OWNER = True


@dataclass(frozen=True)
class AnalyticsOpsRouteHandlers:
    event_store: Any
    snapshot_db_path: str = 'runtime/data/analytics_snapshots.db'
    queue_bridge: AnalyticsFleetQueueJobBridge | None = None

    def materialize_bundle(self, request: AnalyticsMaterializeRequest) -> dict[str, Any]:
        with SqliteAnalyticsSnapshotStore(self.snapshot_db_path, tenant_id=request.tenant_id) as store:
            service = AnalyticsSnapshotService(store=store)
            materializer = AnalyticsMaterializer(event_store=self.event_store, snapshot_service=service)
            return materializer.materialize_for_tenant(
                tenant_id=request.tenant_id,
                window_days=request.window_days,
                export_path=request.export_path,
            )

    def enqueue_materialization(self, request: AnalyticsQueueMaterializeRequest) -> dict[str, Any]:
        if self.queue_bridge is None:
            raise RuntimeError('analytics queue bridge is not configured')
        return self.queue_bridge.enqueue_materialization(
            tenant_id=request.tenant_id,
            window_days=request.window_days,
            queue_name=request.queue_name,
            export_path=request.export_path,
        )

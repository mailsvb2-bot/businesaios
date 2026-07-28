from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from application.analytics.analytics_export_path_policy import AnalyticsExportPathPolicy
from application.analytics.analytics_export_service import AnalyticsExportService
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
    export_root: str = 'runtime/data/analytics_exports'
    queue_bridge: AnalyticsFleetQueueJobBridge | None = None

    def materialize_bundle(self, request: AnalyticsMaterializeRequest) -> dict[str, Any]:
        with SqliteAnalyticsSnapshotStore(self.snapshot_db_path, tenant_id=request.tenant_id) as store:
            service = AnalyticsSnapshotService(store=store)
            materializer = AnalyticsMaterializer(
                event_store=self.event_store,
                snapshot_service=service,
                _export=AnalyticsExportService(export_root=self.export_root),
            )
            return materializer.materialize_for_tenant(
                tenant_id=request.tenant_id,
                window_days=request.window_days,
                export_path=request.export_path,
            )

    def enqueue_materialization(self, request: AnalyticsQueueMaterializeRequest) -> dict[str, Any]:
        if self.queue_bridge is None:
            raise RuntimeError('analytics queue bridge is not configured')
        normalized_export_path = None
        if request.export_path is not None and str(request.export_path).strip():
            normalized_export_path = AnalyticsExportPathPolicy(
                export_root=Path(self.export_root)
            ).normalized_relative_file(
                requested_path=request.export_path,
                tenant_id=request.tenant_id,
            )
        return self.queue_bridge.enqueue_materialization(
            tenant_id=request.tenant_id,
            window_days=request.window_days,
            queue_name=request.queue_name,
            export_path=normalized_export_path,
        )

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from application.analytics.analytics_snapshot_service import AnalyticsSnapshotService
from application.analytics.business_analytics_service import ApplicationBusinessAnalyticsService
from application.analytics.dashboard_service import ApplicationAnalyticsDashboardService
from entrypoints.api.analytics_models import (
    AnalyticsPayloadResponse,
    AnalyticsSnapshotReadRequest,
    AnalyticsSnapshotWriteRequest,
    AnalyticsWindowRequest,
)
from observability.analytics_snapshot_store import SqliteAnalyticsSnapshotStore

CANON_API_ANALYTICS_ROUTE_HANDLERS = True
CANON_API_ANALYTICS_ROUTE_HANDLERS_FINAL_OWNER = True


@dataclass(frozen=True)
class AnalyticsRouteHandlers:
    event_store: Any
    snapshot_db_path: str = 'runtime/data/analytics_snapshots.db'

    def get_business_scorecard(self, *, tenant_id: str, window_days: int = 30) -> dict[str, Any]:
        payload = ApplicationBusinessAnalyticsService(event_store=self.event_store).build_scorecard(
            tenant_id=str(tenant_id),
            window_days=int(window_days),
        )
        plain = asdict(payload) if is_dataclass(payload) else dict(payload)
        return AnalyticsPayloadResponse(payload=plain).as_dict()

    def get_dashboard_bundle(self, *, tenant_id: str, window_days: int = 30) -> dict[str, Any]:
        payload = ApplicationAnalyticsDashboardService(event_store=self.event_store).build_dashboard_bundle(
            tenant_id=str(tenant_id),
            window_days=int(window_days),
        )
        return AnalyticsPayloadResponse(payload=payload).as_dict()

    def write_snapshot(self, request: AnalyticsSnapshotWriteRequest) -> dict[str, Any]:
        with SqliteAnalyticsSnapshotStore(self.snapshot_db_path, tenant_id=request.tenant_id) as store:
            record = AnalyticsSnapshotService(store=store).write_snapshot(
                tenant_id=request.tenant_id,
                snapshot_kind=request.snapshot_kind,
                payload=request.payload,
                snapshot_id=request.snapshot_id,
            )
        return {
            'snapshot_id': record.snapshot_id,
            'tenant_id': record.tenant_id,
            'snapshot_kind': record.snapshot_kind,
            'created_at': record.created_at,
            'content_sha256': record.content_sha256,
        }

    def read_snapshot(self, request: AnalyticsSnapshotReadRequest) -> dict[str, Any]:
        with SqliteAnalyticsSnapshotStore(self.snapshot_db_path) as store:
            record = AnalyticsSnapshotService(store=store).read_snapshot(snapshot_id=request.snapshot_id)
        if record is None:
            raise KeyError(f'analytics snapshot not found: {request.snapshot_id}')
        return {
            'snapshot_id': record.snapshot_id,
            'tenant_id': record.tenant_id,
            'snapshot_kind': record.snapshot_kind,
            'payload': record.payload,
            'created_at': record.created_at,
            'content_sha256': record.content_sha256,
        }

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from application.analytics.analytics_manifest_chain_store import SqliteAnalyticsManifestChainStore
from application.analytics.analytics_signed_export_chain_service import AnalyticsSignedExportChainService
from application.analytics.dashboard_service import ApplicationAnalyticsDashboardService
from entrypoints.api.analytics_models import AnalyticsSignedExportRequest

CANON_API_ANALYTICS_SIGNED_EXPORT_ROUTE_HANDLERS = True
CANON_API_ANALYTICS_SIGNED_EXPORT_ROUTE_HANDLERS_FINAL_OWNER = True


@dataclass(frozen=True)
class AnalyticsSignedExportRouteHandlers:
    event_store: Any
    manifest_chain_db_path: str
    export_root: str

    def export_dashboard_bundle(self, request: AnalyticsSignedExportRequest) -> dict[str, Any]:
        bundle = ApplicationAnalyticsDashboardService(event_store=self.event_store).build_dashboard_bundle(
            tenant_id=str(request.tenant_id),
            window_days=int(request.window_days),
        )
        export_dir = str(request.export_dir or self.export_root)
        with SqliteAnalyticsManifestChainStore(self.manifest_chain_db_path) as chain_store:
            service = AnalyticsSignedExportChainService(manifest_chain_store=chain_store)
            return service.export_signed_bundle(
                export_dir=export_dir,
                export_id=str(request.export_id),
                tenant_id=str(request.tenant_id),
                bundle=bundle,
            )

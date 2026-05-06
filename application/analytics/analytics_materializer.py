from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from application.analytics.analytics_alert_service import AnalyticsAlertService
from application.analytics.analytics_export_service import AnalyticsExportService
from application.analytics.analytics_materialization_policy import AnalyticsMaterializationPolicy
from application.analytics.analytics_snapshot_service import AnalyticsSnapshotService
from application.analytics.dashboard_service import ApplicationAnalyticsDashboardService


@dataclass
class AnalyticsMaterializer:
    event_store: Any
    snapshot_service: AnalyticsSnapshotService
    policy: AnalyticsMaterializationPolicy = AnalyticsMaterializationPolicy()
    _dashboard_service: ApplicationAnalyticsDashboardService = field(init=False)
    _export: AnalyticsExportService = field(default_factory=AnalyticsExportService)
    _alerts: AnalyticsAlertService = field(init=False)

    def __post_init__(self) -> None:
        self._dashboard_service = ApplicationAnalyticsDashboardService(event_store=self.event_store)
        self._alerts = AnalyticsAlertService(policy=self.policy)

    def materialize_for_tenant(self, *, tenant_id: str, window_days: int | None = None, export_path: str | None = None) -> dict:
        resolved = int(window_days or self.policy.default_window_days)
        bundle = self._dashboard_service.build_dashboard_bundle(tenant_id=str(tenant_id), window_days=resolved)
        stored = {
            'business': self.snapshot_service.write_snapshot(tenant_id=str(tenant_id), snapshot_kind='business_scorecard', payload=bundle['business']).snapshot_id,
            'dashboard': self.snapshot_service.write_snapshot(tenant_id=str(tenant_id), snapshot_kind='analytics_dashboard', payload=bundle['dashboard']).snapshot_id,
            'tenant_rollup': self.snapshot_service.write_snapshot(tenant_id=str(tenant_id), snapshot_kind='tenant_rollup', payload=bundle['tenant_rollup']).snapshot_id,
            'explainability': self.snapshot_service.write_snapshot(tenant_id=str(tenant_id), snapshot_kind='analytics_explainability', payload=bundle['explainability']).snapshot_id,
        }
        alerts = self._alerts.build_alert_batch(dashboard_bundle=bundle)
        export_file = self._export.export_bundle(export_path=export_path, bundle=bundle, tenant_id=str(tenant_id)) if export_path else None
        return {'tenant_id': str(tenant_id), 'window_days': resolved, 'stored_snapshots': stored, 'alerts': {'tenant_id': alerts.tenant_id, 'generated_at_ms': alerts.generated_at_ms, 'alerts': [a.__dict__ for a in alerts.alerts]}, 'export_file': export_file}

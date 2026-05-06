from __future__ import annotations

import time
from dataclasses import dataclass

from application.analytics.analytics_materialization_policy import AnalyticsMaterializationPolicy
from observability.analytics_alert_contract import AnalyticsAlert, AnalyticsAlertBatch


@dataclass(frozen=True)
class AnalyticsAlertService:
    policy: AnalyticsMaterializationPolicy = AnalyticsMaterializationPolicy()

    def build_alert_batch(self, *, dashboard_bundle: dict) -> AnalyticsAlertBatch:
        tenant_id = str(dashboard_bundle['dashboard']['tenant_id'])
        alerts: list[AnalyticsAlert] = []
        dashboard = dashboard_bundle['dashboard']
        rollup = dashboard_bundle['tenant_rollup']
        if dashboard['overall_state'] == 'critical' and self.policy.alert_on_critical:
            alerts.append(AnalyticsAlert(alert_id=f'analytics-overall-critical-{tenant_id}', tenant_id=tenant_id, source_kind='dashboard', severity='critical', summary='analytics dashboard is in critical state', metric_id='overall_score', observed_value=float(dashboard['overall_score'])))
        if float(rollup['retention_ratio']) < float(self.policy.retention_floor):
            alerts.append(AnalyticsAlert(alert_id=f'analytics-low-retention-{tenant_id}', tenant_id=tenant_id, source_kind='tenant_rollup', severity='warning', summary='retention ratio fell below floor', metric_id='retention_ratio', threshold_value=float(self.policy.retention_floor), observed_value=float(rollup['retention_ratio'])))
        if float(rollup['execution_ratio']) < float(self.policy.execution_ratio_floor):
            alerts.append(AnalyticsAlert(alert_id=f'analytics-low-execution-{tenant_id}', tenant_id=tenant_id, source_kind='tenant_rollup', severity='warning', summary='execution ratio fell below floor', metric_id='execution_ratio', threshold_value=float(self.policy.execution_ratio_floor), observed_value=float(rollup['execution_ratio'])))
        if float(rollup['blocked_ratio']) > float(self.policy.blocked_ratio_ceiling):
            alerts.append(AnalyticsAlert(alert_id=f'analytics-high-blocking-{tenant_id}', tenant_id=tenant_id, source_kind='tenant_rollup', severity='critical', summary='blocked ratio exceeded ceiling', metric_id='blocked_ratio', threshold_value=float(self.policy.blocked_ratio_ceiling), observed_value=float(rollup['blocked_ratio'])))
        if int(rollup['latency_p95_ms']) > int(self.policy.latency_p95_ceiling_ms):
            alerts.append(AnalyticsAlert(alert_id=f'analytics-high-latency-{tenant_id}', tenant_id=tenant_id, source_kind='tenant_rollup', severity='critical', summary='latency p95 exceeded ceiling', metric_id='latency_p95_ms', threshold_value=float(self.policy.latency_p95_ceiling_ms), observed_value=float(rollup['latency_p95_ms'])))
        return AnalyticsAlertBatch(tenant_id=tenant_id, alerts=tuple(alerts), generated_at_ms=int(time.time() * 1000))

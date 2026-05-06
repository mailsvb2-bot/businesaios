from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.contracts.analytics_rollup import FleetAnalyticsRollup, TenantAnalyticsRollup


@dataclass(frozen=True)
class AnalyticsRollupService:
    def build_tenant_rollup(self, *, dashboard, business_scorecard) -> TenantAnalyticsRollup:
        return TenantAnalyticsRollup(
            tenant_id=str(dashboard.tenant_id),
            overall_state=str(dashboard.overall_state),
            overall_score=float(dashboard.overall_score),
            revenue_total=float(business_scorecard.revenue.revenue_total),
            retention_ratio=float(business_scorecard.retention.retention_ratio),
            execution_ratio=float(business_scorecard.decisions.execution_ratio),
            blocked_ratio=float(business_scorecard.decisions.blocked_ratio),
            latency_p95_ms=int(business_scorecard.latency.p95_ms),
        )

    def build_tenant_rollup_from_bundle(self, *, bundle: Mapping[str, Any]) -> TenantAnalyticsRollup:
        dashboard = dict(bundle.get('dashboard') or {})
        business = dict(bundle.get('business') or {})
        revenue = dict(business.get('revenue') or {})
        retention = dict(business.get('retention') or {})
        decisions = dict(business.get('decisions') or {})
        latency = dict(business.get('latency') or {})
        tenant_id = str(dashboard.get('tenant_id') or business.get('tenant_id') or '').strip()
        if not tenant_id:
            raise ValueError('bundle must contain tenant_id')
        return TenantAnalyticsRollup(
            tenant_id=tenant_id,
            overall_state=str(dashboard.get('overall_state') or 'unknown'),
            overall_score=float(dashboard.get('overall_score') or 0.0),
            revenue_total=float(revenue.get('revenue_total') or 0.0),
            retention_ratio=float(retention.get('retention_ratio') or 0.0),
            execution_ratio=float(decisions.get('execution_ratio') or 0.0),
            blocked_ratio=float(decisions.get('blocked_ratio') or 0.0),
            latency_p95_ms=int(latency.get('p95_ms') or 0),
        )

    def build_fleet_rollup(self, *, tenant_rollups: Iterable[TenantAnalyticsRollup]) -> FleetAnalyticsRollup:
        items = list(tenant_rollups)
        if not items:
            return FleetAnalyticsRollup(
                tenant_count=0,
                healthy_tenants=0,
                warning_tenants=0,
                critical_tenants=0,
                average_score=0.0,
                generated_at_ms=int(time.time() * 1000),
                metadata={'owner': 'core.analytics.analytics_rollup'},
            )
        healthy = sum(1 for i in items if i.overall_state == 'healthy')
        warning = sum(1 for i in items if i.overall_state == 'warning')
        critical = sum(1 for i in items if i.overall_state == 'critical')
        return FleetAnalyticsRollup(
            tenant_count=len(items),
            healthy_tenants=healthy,
            warning_tenants=warning,
            critical_tenants=critical,
            average_score=round(sum(i.overall_score for i in items) / len(items), 4),
            revenue_total=round(sum(i.revenue_total for i in items), 4),
            average_retention_ratio=round(sum(i.retention_ratio for i in items) / len(items), 4),
            average_execution_ratio=round(sum(i.execution_ratio for i in items) / len(items), 4),
            average_blocked_ratio=round(sum(i.blocked_ratio for i in items) / len(items), 4),
            average_latency_p95_ms=round(sum(i.latency_p95_ms for i in items) / len(items), 4),
            top_risk_tenants=tuple(i.tenant_id for i in sorted(items, key=lambda x: (x.overall_score, -x.blocked_ratio, x.latency_p95_ms))[:5]),
            generated_at_ms=int(time.time() * 1000),
            metadata={'owner': 'core.analytics.analytics_rollup'},
        )

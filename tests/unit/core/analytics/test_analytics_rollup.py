from __future__ import annotations

from core.analytics.analytics_rollup import AnalyticsRollupService
from core.contracts.analytics_rollup import TenantAnalyticsRollup


def test_build_tenant_rollup_from_bundle():
    rollup = AnalyticsRollupService().build_tenant_rollup_from_bundle(
        bundle={
            'dashboard': {'tenant_id': 'tenant-1', 'overall_state': 'warning', 'overall_score': 0.6},
            'business': {
                'revenue': {'revenue_total': 42.5},
                'retention': {'retention_ratio': 0.2},
                'decisions': {'execution_ratio': 0.75, 'blocked_ratio': 0.1},
                'latency': {'p95_ms': 1700},
            },
        }
    )
    assert rollup.tenant_id == 'tenant-1'
    assert rollup.revenue_total == 42.5
    assert rollup.latency_p95_ms == 1700


def test_build_fleet_rollup_aggregates_values():
    fleet = AnalyticsRollupService().build_fleet_rollup(
        tenant_rollups=[
            TenantAnalyticsRollup('a', 'healthy', 0.9, 100.0, 0.4, 0.9, 0.05, 900),
            TenantAnalyticsRollup('b', 'warning', 0.6, 50.0, 0.2, 0.7, 0.15, 1800),
        ]
    )
    assert fleet.tenant_count == 2
    assert fleet.revenue_total == 150.0
    assert fleet.top_risk_tenants

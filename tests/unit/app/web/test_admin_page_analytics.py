from __future__ import annotations

from app.web.pages.admin import AdminPage
from observability.slo_contract import SLIKind
from observability.tenant_metrics_registry import MetricAggregation, TenantMetricsRegistry


def _registry() -> TenantMetricsRegistry:
    registry = TenantMetricsRegistry()
    registry.emit(
        tenant_id='tenant-1',
        metric_name='slo.ok',
        kind=SLIKind.THROUGHPUT,
        value=1.0,
        aggregation=MetricAggregation.SUM,
    )
    return registry


def test_admin_page_build_dashboard_includes_analytics_overview() -> None:
    page = AdminPage()
    result = page.build_dashboard(
        tenant_id='tenant-1',
        tenant_records=(),
        approvals=(),
        runtime_alerts=(),
        override=None,
        trace_events=(),
        security_events=(),
        quota_usage={},
        quota_limits={},
        slo_definitions=(),
        metrics_registry=_registry(),
        analytics_bundle={
            'dashboard': {
                'tenant_id': 'tenant-1',
                'overall_state': 'healthy',
                'overall_score': 0.91,
                'window_days': 30,
                'sections': {},
                'highlights': (),
                'risks': (),
            }
        },
    )
    sections = result['payload']['sections']
    assert sections['analytics_overview'] is not None
    assert sections['analytics_overview']['kind'] == 'analytics_dashboard_card'

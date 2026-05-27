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


def test_admin_page_build_dashboard_includes_monetization_overview() -> None:
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
        monetization_snapshot={
            'tenant_id': 'tenant-1',
            'gross_revenue_minor': 10000,
            'refunded_minor': 500,
            'chargeback_minor': 0,
            'net_revenue_minor': 9500,
            'active_subscriptions': 7,
            'past_due_subscriptions': 1,
            'cancelled_subscriptions': 2,
            'currency': 'EUR',
        },
    )
    section = result['payload']['sections']['monetization_overview']
    assert section is not None
    assert section['kind'] == 'monetization_dashboard_card'
    assert section['payload']['net_revenue_minor'] == 9500



def test_admin_page_build_dashboard_includes_revenue_advisory() -> None:
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
        revenue_advisory={
            'tenant_id': 'tenant-1',
            'product_id': 'product-1',
            'generated_at': '2026-04-09T00:00:00+00:00',
            'projected_ltv': 250.0,
            'projected_churn_rate': 0.04,
            'recommended_price_plan_id': 'pro',
            'recommended_price_amount': 39.0,
            'recommended_paywall_variant_id': 'trial-first',
            'recommended_subscription_plan_id': 'pro',
            'highest_blast_radius': 'moderate',
            'approval_required_count': 0,
            'experiments_count': 2,
            'action_mappings_count': 3,
            'flags': {'pricing': True},
        },
    )
    section = result['payload']['sections']['revenue_advisory']
    assert section is not None
    assert section['kind'] == 'revenue_advisory_card'
    assert section['payload']['recommended_paywall_variant_id'] == 'trial-first'

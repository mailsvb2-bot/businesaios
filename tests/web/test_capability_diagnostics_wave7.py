from __future__ import annotations

from app.web.components.capability_diagnostics_card import CapabilityDiagnosticsCard
from app.web.pages.admin import AdminPage
from app.web.pages.runtime_alerts import RuntimeAlertsPage
from observability.slo_contract import SLIKind, SLOComparator, SLODefinition
from observability.tenant_metrics_registry import MetricAggregation, TenantMetricsRegistry
from reliability.execution_reconciliation import ReconciliationReport
from reliability.recovery_orchestrator import RecoveryPlan


def _capability_view() -> dict[str, object]:
    return {
        'diagnostics': {
            'status': 'watch',
            'headline': 'Capability requires attention for launch_campaign.',
            'operator_action': 'monitor',
            'signals': (
                {'code': 'stale_evidence', 'severity': 'high', 'summary': 'Evidence is stale.', 'operator_actionable': True},
                {'code': 'low_confidence', 'severity': 'medium', 'summary': 'Confidence is low.', 'operator_actionable': False},
            ),
        },
        'policy_verdict': {'allowed': True, 'recommended_autonomy_tier': 'bounded_autonomy'},
        'execution_verdict': {'allowed': True, 'operator_required': False},
    }


def test_capability_diagnostics_card_builds_summary() -> None:
    card = CapabilityDiagnosticsCard().build_from_capability_view(tenant_id='tenant-a', capability_view=_capability_view())
    assert card is not None
    assert card['kind'] == 'capability_diagnostics_card'
    assert card['payload']['signal_count'] == 2
    assert card['payload']['summary']['high_count'] == 1


def test_admin_and_runtime_alert_pages_surface_capability_diagnostics() -> None:
    registry = TenantMetricsRegistry()
    registry.emit(tenant_id='tenant-a', metric_name='runtime.success_rate', kind=SLIKind.SUCCESS_RATE, value=0.98, aggregation=MetricAggregation.AVG)
    slo = SLODefinition(slo_id='slo-1', tenant_id='tenant-a', sli_name='runtime.success_rate', sli_kind=SLIKind.SUCCESS_RATE, comparator=SLOComparator.GTE, target_value=0.95)
    page = AdminPage().build_dashboard(
        tenant_id='tenant-a',
        tenant_records=(),
        approvals=(),
        runtime_alerts=(),
        override=None,
        trace_events=(),
        security_events=(),
        quota_usage={'actions': 1},
        quota_limits={'actions': 10},
        slo_definitions=(slo,),
        metrics_registry=registry,
        capability_view=_capability_view(),
    )
    assert page['payload']['sections']['capability_diagnostics']['kind'] == 'capability_diagnostics_card'

    recovery_plan = RecoveryPlan(
        run_id='run-1',
        recovery_action='resume',
        reason='checkpoint present',
        reconciliation=ReconciliationReport(run_id='run-1', latest_stage='execution', idempotency_state='running', outbox_state='pending', checkpoint_count=1),
    )
    runtime_page = RuntimeAlertsPage().build_runtime_view(
        tenant_id='tenant-a',
        alerts=(),
        slo_definitions=(slo,),
        metrics_registry=registry,
        recovery_plan=recovery_plan,
        capability_view=_capability_view(),
    )
    assert runtime_page['payload']['capability_diagnostics']['kind'] == 'capability_diagnostics_card'

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, UTC

from app.web.components.autonomy_budget_panel import AutonomyBudgetPanel
from app.web.components.dead_letter_panel import DeadLetterPanel
from app.web.components.recovery_panel import RecoveryPanel
from app.web.components.run_control_panel import RunControlPanel
from app.web.pages.admin import AdminPage
from app.web.pages.runtime_alerts import RuntimeAlertsPage
from observability.slo_contract import SLIKind, SLOComparator, SLODefinition
from observability.tenant_metrics_registry import MetricAggregation, TenantMetricsRegistry
from reliability.execution_reconciliation import ReconciliationReport
from reliability.outbox_store import OutboxMessage, OutboxState
from reliability.recovery_orchestrator import RecoveryPlan, TransportRecoveryResult
from tenancy.tenant_contract import TenantQuotaCheck
from tenancy.tenant_execution_budget_guard import (
    TenantExecutionBudgetVerdict,
    TenantExecutionUsage,
    TenantRuntimeLimitCheck,
)


@dataclass(frozen=True)
class _Run:
    run_id: str
    trace_id: str
    tenant_id: str
    goal: str = 'grow revenue'
    status: str = 'running'
    stage: str = 'execution'
    decision_id: str | None = 'dec-1'
    action_id: str | None = 'act-1'
    operator_locked: bool = False
    human_approval_required: bool = True
    risk_flags: tuple[str, ...] = ('approval_required',)


@dataclass(frozen=True)
class _Event:
    tenant_id: str
    trace_id: str
    run_id: str
    sequence_no: int
    stage: str = 'execution'
    event_type: str = 'executor.started'
    summary: str = 'started'


def _recovery_plan() -> RecoveryPlan:
    return RecoveryPlan(
        run_id='run-1',
        recovery_action='resume',
        reason='checkpoint present',
        reconciliation=ReconciliationReport(
            run_id='run-1',
            latest_stage='execution',
            idempotency_state='running',
            outbox_state='pending',
            checkpoint_count=2,
            anomalies=('late_stage_without_outbox_record',),
        ),
        anomalies=('late_stage_without_outbox_record',),
        operator_required=True,
        operator_hint='inspect runtime',
        resume_action='resume',
        resume_stage='verification',
        risk_flags=('manual_review',),
    )


def test_run_control_panel_filters_cross_tenant_events_and_dedupes_controls() -> None:
    panel = RunControlPanel().build_from_snapshot(
        tenant_id='tenant-a',
        run_snapshot=_Run(run_id='run-1', trace_id='trace-1', tenant_id='tenant-a'),
        allowed_controls=('resume', 'resume', {'code': 'pause', 'enabled': False}),
        recent_events=(
            _Event(tenant_id='tenant-a', trace_id='trace-1', run_id='run-1', sequence_no=1),
            _Event(tenant_id='tenant-b', trace_id='trace-1', run_id='run-1', sequence_no=2),
        ),
        recovery_plan=_recovery_plan(),
    )
    assert panel['payload']['summary']['enabled_control_count'] == 1
    assert len(panel['payload']['controls']) == 2
    assert len(panel['payload']['recent_events']) == 1


def test_dead_letter_and_recovery_panels_render_canonical_state() -> None:
    now = datetime.now(UTC)
    message = OutboxMessage(
        tenant_id='tenant-a',
        message_id='msg-1',
        topic='email.send',
        dedupe_key='d-1',
        payload={'token': 'secret'},
        state=OutboxState.DEAD,
        created_at=now,
        updated_at=now,
        available_at=now,
        run_id='run-1',
        trace_id='trace-1',
        delivery_attempts=3,
        last_error='timeout',
    )
    dead = DeadLetterPanel().build_from_entries(tenant_id='tenant-a', entries=(message,))
    recovery = RecoveryPanel().build_from_plan(
        tenant_id='tenant-a',
        plan=_recovery_plan(),
        transport_results=(TransportRecoveryResult('smtp', 'worker-1', 'smtp-backend', 4, 2, 1, 1, 0),),
    )
    assert dead['payload']['summary']['dead_state_count'] == 1
    assert dead['payload']['rows'][0]['payload']['token'] == '***REDACTED***'
    assert recovery['payload']['summary']['requires_operator_attention'] is True
    assert recovery['payload']['summary']['dead_lettered'] == 1


def test_autonomy_budget_panel_renders_runtime_and_quota_checks() -> None:
    usage = TenantExecutionUsage(tenant_id='tenant-a', action_count=3, connector_call_count=2, budget_delta=4.5)
    verdict = TenantExecutionBudgetVerdict(
        allowed=False,
        reason='tenant_execution_budget_denied',
        tenant_id='tenant-a',
        violations=('max_actions_per_run', 'quota:actions_per_day'),
        runtime_limit_checks={
            'max_actions_per_run': TenantRuntimeLimitCheck(
                name='max_actions_per_run', allowed=False, requested=3.0, limit=1.0
            )
        },
        quota_checks={
            'actions_per_day': TenantQuotaCheck(
                allowed=False,
                reason='quota exceeded',
                tenant_id='tenant-a',
                dimension='actions_per_day',
                requested=3.0,
                used=2.0,
                limit=4.0,
                remaining=2.0,
                retry_after_seconds=86400,
            )
        },
        consumed=False,
    )
    panel = AutonomyBudgetPanel().build_from_verdict(tenant_id='tenant-a', usage=usage, verdict=verdict)
    assert panel['payload']['summary']['total_violation_count'] == 2
    assert panel['payload']['summary']['operator_attention_required'] is True


def test_admin_and_runtime_alert_pages_include_operator_sections() -> None:
    registry = TenantMetricsRegistry()
    registry.emit(tenant_id='tenant-a', metric_name='runtime.success_rate', kind=SLIKind.SUCCESS_RATE, value=0.99, aggregation=MetricAggregation.AVG)
    slo = SLODefinition(
        slo_id='slo-1',
        tenant_id='tenant-a',
        sli_name='runtime.success_rate',
        sli_kind=SLIKind.SUCCESS_RATE,
        comparator=SLOComparator.GTE,
        target_value=0.95,
    )
    now = datetime.now(UTC)
    page = AdminPage().build_dashboard(
        tenant_id='tenant-a',
        tenant_records=(),
        approvals=(),
        runtime_alerts=(),
        override=None,
        trace_events=(_Event(tenant_id='tenant-a', trace_id='trace-1', run_id='run-1', sequence_no=1),),
        security_events=(),
        quota_usage={'actions': 1},
        quota_limits={'actions': 10},
        slo_definitions=(slo,),
        metrics_registry=registry,
        run_snapshot=_Run(run_id='run-1', trace_id='trace-1', tenant_id='tenant-a'),
        recovery_plan=_recovery_plan(),
        dead_letter_entries=(OutboxMessage(tenant_id='tenant-a', message_id='msg-1', topic='email.send', dedupe_key='d-1', payload={}, state=OutboxState.DEAD, created_at=now, updated_at=now, available_at=now),),
        budget_usage=TenantExecutionUsage(tenant_id='tenant-a', action_count=1),
        budget_verdict=TenantExecutionBudgetVerdict(allowed=True, reason='ok', tenant_id='tenant-a'),
        transport_results=(TransportRecoveryResult('smtp', 'worker-1', 'smtp-backend', 1, 1, 0, 0, 0),),
    )
    sections = page['payload']['sections']
    assert sections['run_control']['kind'] == 'run_control_panel'
    assert sections['dead_letter']['kind'] == 'dead_letter_panel'
    assert sections['autonomy_budget']['kind'] == 'autonomy_budget_panel'
    assert sections['recovery']['kind'] == 'recovery_panel'

    runtime_page = RuntimeAlertsPage().build_runtime_view(
        tenant_id='tenant-a',
        alerts=(),
        slo_definitions=(slo,),
        metrics_registry=registry,
        recovery_plan=_recovery_plan(),
        dead_letter_entries=(),
        transport_results=(),
    )
    assert runtime_page['payload']['recovery']['kind'] == 'recovery_panel'
    assert runtime_page['payload']['dead_letter']['kind'] == 'dead_letter_panel'

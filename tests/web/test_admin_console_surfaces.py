from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.web.components.approval_queue_card import ApprovalQueueCard
from app.web.components.audit_log_table import AuditLogTable
from app.web.components.runtime_alerts_card import RuntimeAlertsCard
from app.web.components.security_events_card import SecurityEventsCard
from app.web.pages.admin import AdminPage
from app.web.pages.approvals import ApprovalsPage
from app.web.pages.connector_admin import ConnectorAdminPage
from observability.slo_contract import SLIKind, SLOComparator, SLODefinition
from observability.tenant_metrics_registry import MetricAggregation, TenantMetricsRegistry


@dataclass(frozen=True)
class _ApprovalRequest:
    approval_id: str
    tenant_id: str
    subject_type: str = 'deployment'
    subject_id: str = 'dep-1'
    requested_by: str = 'operator'
    reason: str = 'review'
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    required_role_groups: tuple[tuple[str, ...], ...] = (('admin',),)
    min_distinct_approvers: int = 1
    prohibit_self_approval: bool = True
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _ApprovalRecord:
    request: _ApprovalRequest
    status: str = 'requested'
    decisions: tuple[object, ...] = ()
    final_reason: str | None = None


@dataclass(frozen=True)
class _AuditEvent:
    audit_id: str
    tenant_id: str
    event_type: str = 'security.login'
    category: str = 'security'
    severity: str = 'critical'
    emitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor_id: str = 'user-1'
    source_component: str = 'web'
    source_namespace: str = 'app.web'
    trace_id: str = 'trace-1'
    run_id: str | None = None
    decision_id: str | None = None
    action_id: str | None = None
    correlation_id: str | None = None
    subject_type: str | None = 'session'
    subject_id: str | None = 'sess-1'
    tags: tuple[str, ...] = ('auth',)
    payload: dict[str, object] = field(default_factory=lambda: {'password': 'secret'})
    metadata: dict[str, object] = field(default_factory=lambda: {'email': 'user@example.com'})


@dataclass(frozen=True)
class _Incident:
    incident_id: str
    tenant_id: str
    signal_type: str = 'latency'
    status: str = 'open'
    severity: str = 'critical'
    trace_id: str | None = 'trace-1'
    rule_id: str | None = 'rule-1'
    summary: str = 'p95 high'
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, object] = field(default_factory=lambda: {'token': 'abc'})


class _ApprovalStore:
    def __init__(self, records):
        self._records = tuple(records)

    def list_open(self, *, tenant_id: str):
        return tuple(r for r in self._records if r.request.tenant_id == tenant_id)


def test_approval_queue_card_filters_cross_tenant_records() -> None:
    card = ApprovalQueueCard()
    rows = card.build_from_records(
        tenant_id='tenant-a',
        records=(
            _ApprovalRecord(_ApprovalRequest('a1', 'tenant-a')),
            _ApprovalRecord(_ApprovalRequest('a2', 'tenant-b')),
        ),
    )
    assert rows['payload']['count'] == 1
    assert rows['payload']['rows'][0]['approval_id'] == 'a1'


def test_audit_and_security_cards_redact_sensitive_fields() -> None:
    event = _AuditEvent(audit_id='evt-1', tenant_id='tenant-a')
    audit = AuditLogTable().build_from_events(tenant_id='tenant-a', events=(event,))
    security = SecurityEventsCard().build_from_events(tenant_id='tenant-a', events=(event,))
    assert audit['payload']['rows'][0]['payload']['password'] == '***REDACTED***'
    assert audit['payload']['rows'][0]['metadata']['email'] == '<redacted>'
    assert security['payload']['events'][0]['payload']['password'] == '***REDACTED***'


def test_runtime_alerts_card_redacts_payload_and_counts_summary() -> None:
    card = RuntimeAlertsCard().build_from_incidents(
        tenant_id='tenant-a',
        alerts=(_Incident('i1', 'tenant-a'), _Incident('i2', 'tenant-a', status='acknowledged', severity='warning')),
    )
    assert card['payload']['alert_count'] == 2
    assert card['payload']['summary']['critical_count'] == 1
    assert card['payload']['alerts'][0]['payload']['token'] == '***REDACTED***'


def test_approvals_page_uses_store_without_decision_logic() -> None:
    page = ApprovalsPage().build_from_store(
        tenant_id='tenant-a',
        approval_store=_ApprovalStore((_ApprovalRecord(_ApprovalRequest('a1', 'tenant-a')),)),
    )
    assert page['kind'] == 'approvals_page'
    assert page['payload']['queue']['payload']['count'] == 1


def test_admin_page_builds_tenant_bound_dashboard() -> None:
    registry = TenantMetricsRegistry()
    registry.emit(
        tenant_id='tenant-a',
        metric_name='runtime.success_rate',
        kind=SLIKind.SUCCESS_RATE,
        value=0.99,
        aggregation=MetricAggregation.AVG,
    )
    slo = SLODefinition(
        slo_id='slo-1',
        tenant_id='tenant-a',
        sli_name='runtime.success_rate',
        sli_kind=SLIKind.SUCCESS_RATE,
        comparator=SLOComparator.GTE,
        target_value=0.95,
    )
    page = AdminPage().build_dashboard(
        tenant_id='tenant-a',
        tenant_records=(),
        approvals=(_ApprovalRecord(_ApprovalRequest('a1', 'tenant-a')),),
        runtime_alerts=(_Incident('i1', 'tenant-a'),),
        override=None,
        trace_events=(),
        security_events=(_AuditEvent(audit_id='evt-1', tenant_id='tenant-a'),),
        quota_usage={'actions': 5},
        quota_limits={'actions': 10},
        slo_definitions=(slo,),
        metrics_registry=registry,
    )
    assert page['kind'] == 'admin_page'
    assert page['payload']['tenant_id'] == 'tenant-a'
    assert page['payload']['sections']['slo_status']['payload']['non_compliant_count'] == 0


def test_connector_admin_page_normalizes_registry_rows() -> None:
    page = ConnectorAdminPage().build_from_registry(
        tenant_id='tenant-a',
        connectors={
            'hubspot': {'status': 'implemented', 'read': True, 'write': True, 'verify': True, 'production_ready': True, 'action_types': ('sync', 'create')},
        },
    )
    assert page['payload']['implemented_count'] == 1
    assert page['payload']['production_ready_count'] == 1

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from datetime import datetime

from app.web.components.queue_health_card import QueueHealthCard
from app.web.components.queue_remediation_audit_card import QueueRemediationAuditCard
from app.web.pages.queue_ops import QueueOpsPage
from app.web.routes import Routes
from runtime.queue.queue_alerts import QueueAlert
from runtime.queue.queue_slo import QueueSLOReport


@dataclass(frozen=True)
class _Report:
    tenant_id: str = 'tenant-a'
    queue_name: str = 'primary'
    ok: bool = False
    status: str = 'critical'
    reasons: tuple[str, ...] = ('leadership_stale',)
    pending_jobs: int = 12
    active_claims: int = 3
    dead_letter_jobs: int = 1
    janitor_stale_seconds: int | None = 40
    leader_stale_seconds: int | None = 40


def test_queue_health_card_builds_summary() -> None:
    payload = QueueHealthCard().build_from_reports(tenant_id='tenant-a', reports=(_Report(),))
    assert payload['kind'] == 'queue_health_card'
    assert payload['payload']['critical_count'] == 1
    assert payload['payload']['rows'][0]['queue_name'] == 'primary'


def test_queue_ops_page_builds_runtime_view() -> None:
    alert = QueueAlert(
        tenant_id='tenant-a',
        queue_name='primary',
        code='leadership_stale',
        severity='critical',
        message='Queue leadership appears stale',
        created_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    approval = SimpleNamespace(
        request=SimpleNamespace(
            approval_id='ap-1',
            tenant_id='tenant-a',
            subject_type='queue_remediation',
            subject_id='primary',
            requested_by='operator-1',
            reason='Needs manual review',
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            expires_at=None,
            required_role_groups=(('operator',),),
            min_distinct_approvers=1,
            prohibit_self_approval=True,
            metadata={},
        ),
        decisions=(),
        status='requested',
        final_reason=None,
    )
    page = QueueOpsPage().build_runtime_view(tenant_id='tenant-a', reports=(_Report(),), alerts=(alert,), remediation_analytics={'plan_count': 1, 'execution_count': 0}, remediation_audit={'rows': ({'entry_type': 'route_event', 'action': 'get_queue_ops_view', 'recorded_at': '2026-01-01T00:00:00'},)}, approvals=(approval,), operator_summary={'published_alert_count': 1}, timeline_preview=({'entry_type': 'route_event', 'title': 'get_queue_ops_view', 'at': '2026-01-01T00:00:00'},), approval_preview={'approval_required_count': 2}, trend_preview={'pending_direction': 'up'}, data_freshness={'state': 'fresh'}, evidence_timeline=({'entry_type': 'health_sample', 'title': 'Queue health sampled', 'at': '2026-01-01T00:00:00'},), consistency={'state': 'ok'})
    assert page['kind'] == 'queue_ops_page'
    assert page['payload']['queue_health']['payload']['critical_count'] == 1
    assert page['payload']['runtime_alerts']['payload']['alert_count'] == 1
    assert page['payload']['queue_remediation_analytics']['kind'] == 'queue_remediation_analytics_card'
    assert page['payload']['queue_remediation_audit']['kind'] == 'queue_remediation_audit_card'
    assert page['payload']['approval_queue']['kind'] == 'approval_queue_card'
    assert page['payload']['operator_summary']['published_alert_count'] == 1
    assert page['payload']['timeline_preview'][0]['title'] == 'get_queue_ops_view'
    assert page['payload']['approval_preview']['approval_required_count'] == 2
    assert page['payload']['trend_preview']['pending_direction'] == 'up'
    assert page['payload']['data_freshness']['state'] == 'fresh'
    assert page['payload']['evidence_timeline'][0]['entry_type'] == 'health_sample'
    assert page['payload']['consistency']['state'] == 'ok'


def test_queue_ops_route_is_present() -> None:
    payload = Routes().build_default(tenant_id='tenant-a')
    paths = {row['path'] for row in payload['payload']['routes']}
    assert '/web/queue-ops' in paths



def test_queue_health_card_builds_from_mapping_reports() -> None:
    payload = QueueHealthCard().build_from_reports(
        tenant_id='tenant-a',
        reports=({
            'tenant_id': 'tenant-a',
            'queue_name': 'primary',
            'status': 'critical',
            'pending_jobs': 10,
            'approval_preview': {'approval_required_count': 2},
            'data_freshness': {'state': 'stale'},
        },),
    )
    assert payload['payload']['approval_required_total'] == 2
    assert payload['payload']['stale_queue_count'] == 1


def test_queue_remediation_audit_card_counts_redacted_rows() -> None:
    card = QueueRemediationAuditCard()
    payload = card.build({'tenant_id': 'tenant-a', 'queue_name': 'ops', 'rows': ({'entry_type': 'route_event', 'metadata': {'token': '[redacted]'}},)})
    assert payload['payload']['redacted_row_count'] == 1

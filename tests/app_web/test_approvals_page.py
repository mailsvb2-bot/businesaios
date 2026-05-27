from __future__ import annotations

from app.web.pages.approvals import ApprovalsPage
from governance.approval_store import InMemoryApprovalStore
from governance.rbac_contract import RoleId
from interfaces.api.approval_route_handlers import ApprovalRouteHandlers


def test_approvals_page_reports_execution_summary() -> None:
    store = InMemoryApprovalStore()
    handlers = ApprovalRouteHandlers(approval_store=store)
    handlers.submit_execution_approval(
        tenant_id='tenant-a',
        execution_id='exec-1',
        decision_id='dec-1',
        action_name='send_email',
        requested_by='user-1',
        reason='approval required',
        required_role_groups=((RoleId.OWNER,), (RoleId.OPERATOR,)),
        min_distinct_approvers=2,
        subject_fingerprint='fp-1',
    )
    page = ApprovalsPage().build_from_store(tenant_id='tenant-a', approval_store=store)
    assert page['kind'] == 'approvals_page'
    payload = page['payload']
    assert payload['summary']['execution_pending_count'] == 1
    assert payload['summary']['fingerprint_bound_count'] == 1
    assert payload['summary']['dual_control_count'] == 1


def test_approvals_page_counts_only_requested_execution_rows_as_pending() -> None:
    page = ApprovalsPage().build(
        {
            'tenant_id': 'tenant-a',
            'queue': {
                'rows': (
                    {
                        'approval_id': 'ap-1',
                        'tenant_id': 'tenant-a',
                        'subject_type': 'action_execution',
                        'status': 'requested',
                        'min_distinct_approvers': 2,
                        'metadata': {'subject_fingerprint': 'fp-1', 'decision_id': 'dec-1', 'action_name': 'send_email'},
                    },
                    {
                        'approval_id': 'ap-2',
                        'tenant_id': 'tenant-a',
                        'subject_type': 'action_execution',
                        'status': 'approved',
                        'min_distinct_approvers': 1,
                        'metadata': {'subject_fingerprint': 'fp-2', 'decision_id': 'dec-2', 'action_name': 'publish'},
                    },
                )
            },
        }
    )
    summary = page['payload']['summary']
    assert summary['execution_pending_count'] == 1
    assert summary['fingerprint_bound_count'] == 1
    assert summary['action_bound_count'] == 1
    assert summary['decision_bound_count'] == 1
    assert summary['dual_control_count'] == 1


def test_approvals_page_exposes_operator_console_actions() -> None:
    page = ApprovalsPage().build(
        {
            'tenant_id': 'tenant-a',
            'queue': {
                'rows': (
                    {
                        'approval_id': 'ap-1',
                        'tenant_id': 'tenant-a',
                        'subject_type': 'action_execution',
                        'status': 'requested',
                        'min_distinct_approvers': 1,
                        'metadata': {'subject_fingerprint': 'fp-1', 'decision_id': 'dec-1', 'action_name': 'send_email'},
                    },
                )
            },
        }
    )
    payload = page['payload']
    assert payload['operator_console']['action_required'] is True
    assert payload['queue_actions'][0]['decision_id'] == 'dec-1'


def test_approvals_page_exposes_open_operator_overrides() -> None:
    page = ApprovalsPage().build(
        {
            'tenant_id': 'tenant-a',
            'queue': {'rows': ()},
            'operator_overrides': {
                'records': (
                    {
                        'override_id': 'ovr-1',
                        'tenant_id': 'tenant-a',
                        'execution_id': 'exec-1',
                        'decision_id': 'dec-1',
                        'action_name': 'send_email',
                        'subject_fingerprint': 'fp-1',
                        'status': 'requested',
                        'metadata': {'impact_category': 'outbound'},
                    },
                ),
            },
        }
    )
    payload = page['payload']
    assert payload['summary']['open_override_count'] == 1
    assert payload['summary']['override_actionable_count'] == 1
    assert payload['operator_console']['pending_operator_overrides'] == 1
    assert payload['override_actions'][0]['execution_id'] == 'exec-1'


def test_approvals_page_marks_action_required_for_operator_overrides() -> None:
    page = ApprovalsPage().build(
        {
            'tenant_id': 'tenant-a',
            'queue': {'rows': ()},
            'operator_overrides': {
                'records': (
                    {
                        'override_id': 'ovr-2',
                        'tenant_id': 'tenant-a',
                        'execution_id': 'exec-2',
                        'decision_id': 'dec-2',
                        'action_name': 'publish',
                        'subject_fingerprint': 'fp-2',
                        'status': 'requested',
                        'expires_at': '2030-01-01T00:00:00+00:00',
                    },
                ),
            },
        }
    )
    payload = page['payload']
    assert payload['operator_console']['action_required'] is True
    assert payload['operator_console']['expiring_operator_overrides'] == 1
    assert payload['summary']['override_fingerprint_bound_count'] == 1




def test_approvals_page_reports_resume_candidates() -> None:
    page = ApprovalsPage().build(
        {
            'tenant_id': 'tenant-a',
            'queue': {'rows': ({
                'approval_id': 'ap-approved',
                'tenant_id': 'tenant-a',
                'subject_type': 'action_execution',
                'status': 'approved',
                'metadata': {'subject_fingerprint': 'fp-a', 'decision_id': 'dec-a', 'action_name': 'send_email'},
            },)},
            'operator_overrides': {'records': ({
                'override_id': 'ovr-approved',
                'tenant_id': 'tenant-a',
                'execution_id': 'exec-a',
                'decision_id': 'dec-a',
                'action_name': 'send_email',
                'subject_fingerprint': 'fp-a',
                'status': 'approved',
                'decision': {'resolution': 'approve_once'},
            },)},
        }
    )
    payload = page['payload']
    assert payload['operator_console']['resume_candidate_count'] == 2
    assert payload['summary']['resume_candidate_count'] == 2


def test_approvals_page_uses_history_lifecycle_counts_from_queue_payload() -> None:
    page = ApprovalsPage().build(
        {
            'tenant_id': 'tenant-a',
            'queue': {
                'rows': [],
                'summary': {
                    'history_count': 3,
                    'lifecycle_counts': {'requested': 0, 'approved': 2, 'rejected': 0, 'expired': 1, 'cancelled': 0, 'consumed': 0},
                    'resume_candidate_count': 2,
                    'dual_control_count': 1,
                },
            },
            'operator_overrides': {
                'records': [],
                'summary': {
                    'history_count': 2,
                    'lifecycle_counts': {'requested': 0, 'approved': 1, 'rejected': 0, 'expired': 0, 'cancelled': 0, 'consumed': 1},
                    'resume_candidate_count': 1,
                },
            },
        }
    )
    payload = page['payload']
    assert payload['summary']['history_count'] == 5
    assert payload['summary']['status_counts']['approved'] == 2
    assert payload['summary']['status_counts']['expired'] == 1
    assert payload['summary']['status_counts']['consumed'] == 1
    assert payload['summary']['resume_candidate_count'] == 3



def test_approvals_page_surfaces_audit_resume_counts() -> None:
    page = ApprovalsPage().build(
        {
            'tenant_id': 'tenant-a',
            'queue': {'rows': []},
            'operator_overrides': {'records': []},
            'audit': {
                'count': 4,
                'lifecycle_counts': {
                    'approval_required': 1,
                    'resume_hint_emitted': 1,
                    'resume_ready': 2,
                },
                'recent_events': (
                    {'event_type': 'governance_execution_resume_ready'},
                    {'event_type': 'governance_execution_resume_ready'},
                ),
            },
        }
    )
    payload = page['payload']
    assert payload['operator_console']['resume_ready_event_count'] == 2
    assert payload['summary']['resume_ready_event_count'] == 2
    assert payload['audit']['count'] == 4


def test_approvals_page_surfaces_audit_integrity() -> None:
    page = ApprovalsPage().build(
        {
            'tenant_id': 'tenant-a',
            'queue': {'payload': {'rows': (), 'summary': {}}},
            'audit': {
                'count': 3,
                'lifecycle_counts': {'resume_ready': 2},
                'integrity': {'checked': True, 'valid': True, 'event_count': 3, 'chain_head': 'abc', 'error': None},
                'recent_events': (),
            },
        }
    )
    assert page['payload']['summary']['audit_integrity_valid'] is True
    assert page['payload']['summary']['audit_event_count'] == 3
    assert page['payload']['operator_console']['audit_integrity_valid'] is True



def test_approvals_page_merges_recent_timeline_from_queue_and_overrides() -> None:
    page = ApprovalsPage().build(
        {
            'tenant_id': 'tenant-a',
            'queue': {
                'rows': (),
                'timeline': ({
                    'kind': 'approval',
                    'ref_id': 'ap-1',
                    'status': 'approved',
                    'decision_id': 'dec-old',
                    'emitted_at': '2026-03-29T09:00:00+00:00',
                },),
            },
            'operator_overrides': {
                'records': (),
                'timeline': ({
                    'kind': 'operator_override',
                    'ref_id': 'ovr-1',
                    'status': 'approved',
                    'decision_id': 'dec-new',
                    'emitted_at': '2026-03-29T10:00:00+00:00',
                },),
            },
        }
    )
    payload = page['payload']
    assert payload['summary']['timeline_count'] == 2
    assert payload['operator_console']['timeline_count'] == 2
    assert payload['timeline'][0]['decision_id'] == 'dec-new'
    assert payload['timeline'][1]['decision_id'] == 'dec-old'

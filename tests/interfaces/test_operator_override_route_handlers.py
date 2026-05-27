from __future__ import annotations

from datetime import timedelta

import pytest

from execution.operator_override_contract import OperatorOverrideResolution
from execution.operator_override_store import InMemoryOperatorOverrideStore
from governance.approval_store import InMemoryApprovalStore
from governance.rbac_contract import RoleId
from interfaces.api.approval_route_handlers import ApprovalRouteHandlers


def test_operator_override_submit_list_and_decide_flow() -> None:
    handlers = ApprovalRouteHandlers(
        approval_store=InMemoryApprovalStore(),
        operator_override_store=InMemoryOperatorOverrideStore(),
    )
    record = handlers.submit_operator_override(
        tenant_id='tenant-a',
        execution_id='exec-1',
        decision_id='dec-1',
        action_name='send_email',
        requested_by='user-1',
        reason='need one-shot override',
        subject_fingerprint='fp-1',
        metadata={'impact_category': 'outbound'},
    )
    assert record['status'] == 'requested'
    listing = handlers.list_open_operator_overrides(tenant_id='tenant-a')
    assert listing['summary']['open_override_count'] == 1
    assert listing['summary']['fingerprint_bound_count'] == 1
    assert listing['operator_actions'][0]['action_name'] == 'send_email'

    decided = handlers.decide_operator_override(
        override_id=record['override_id'],
        tenant_id='tenant-a',
        actor_id='owner-1',
        role_id=RoleId.OWNER,
        resolution=OperatorOverrideResolution.APPROVE_ONCE,
        note='approved for one execution',
    )
    assert decided['status'] == 'approved'
    assert decided['decision']['resolution'] == 'approve_once'


def test_operator_override_rejects_unauthorized_role() -> None:
    handlers = ApprovalRouteHandlers(
        approval_store=InMemoryApprovalStore(),
        operator_override_store=InMemoryOperatorOverrideStore(),
    )
    record = handlers.submit_operator_override(
        tenant_id='tenant-a',
        execution_id='exec-1',
        decision_id='dec-1',
        action_name='publish',
        requested_by='user-1',
        reason='need override',
        subject_fingerprint='fp-1',
    )
    with pytest.raises(RuntimeError, match='operator_override_role_not_authorized'):
        handlers.decide_operator_override(
            override_id=record['override_id'],
            tenant_id='tenant-a',
            actor_id='viewer-1',
            role_id=RoleId.VIEWER,
            resolution=OperatorOverrideResolution.APPROVE_ONCE,
            note='nope',
        )


def test_operator_override_get_and_console_summary() -> None:
    handlers = ApprovalRouteHandlers(
        approval_store=InMemoryApprovalStore(),
        operator_override_store=InMemoryOperatorOverrideStore(),
    )
    record = handlers.submit_operator_override(
        tenant_id='tenant-a',
        execution_id='exec-2',
        decision_id='dec-2',
        action_name='publish',
        requested_by='user-2',
        reason='need override',
        subject_fingerprint='fp-2',
    )
    fetched = handlers.get_operator_override(override_id=record['override_id'])
    assert fetched is not None
    assert fetched['execution_id'] == 'exec-2'
    listing = handlers.list_open_operator_overrides(tenant_id='tenant-a')
    assert listing['operator_console']['action_required'] is True
    assert listing['operator_console']['pending_operator_overrides'] == 1
    assert listing['summary']['operator_actionable_count'] == 1




def test_operator_override_listing_expires_stale_records() -> None:
    handlers = ApprovalRouteHandlers(
        approval_store=InMemoryApprovalStore(),
        operator_override_store=InMemoryOperatorOverrideStore(),
    )
    handlers.submit_operator_override(
        tenant_id='tenant-a',
        execution_id='exec-expired',
        decision_id='dec-expired',
        action_name='publish',
        requested_by='user-2',
        reason='expires soon',
        subject_fingerprint='fp-expired',
        expires_at=__import__('execution.operator_override_contract', fromlist=['utc_now']).utc_now() + timedelta(milliseconds=1),
    )
    import time
    time.sleep(0.01)
    listing = handlers.list_open_operator_overrides(tenant_id='tenant-a')
    assert listing['count'] == 0
    assert listing['operator_console']['action_required'] is False
    assert listing['summary']['lifecycle_counts']['expired'] == 1


def test_operator_override_listing_exposes_resume_candidates_after_approval() -> None:
    handlers = ApprovalRouteHandlers(
        approval_store=InMemoryApprovalStore(),
        operator_override_store=InMemoryOperatorOverrideStore(),
    )
    record = handlers.submit_operator_override(
        tenant_id='tenant-a',
        execution_id='exec-3',
        decision_id='dec-3',
        action_name='publish',
        requested_by='user-2',
        reason='need override',
        subject_fingerprint='fp-3',
    )
    handlers.decide_operator_override(
        override_id=record['override_id'],
        tenant_id='tenant-a',
        actor_id='owner-1',
        role_id=RoleId.OWNER,
        resolution=OperatorOverrideResolution.APPROVE_ONCE,
        note='approved once',
    )
    fetched = handlers.get_operator_override(override_id=record['override_id'])
    assert fetched is not None
    assert fetched['status'] == 'approved'


def test_operator_override_listing_reports_history_lifecycle_without_cross_tenant_leak() -> None:
    handlers = ApprovalRouteHandlers(
        approval_store=InMemoryApprovalStore(),
        operator_override_store=InMemoryOperatorOverrideStore(),
    )
    first = handlers.submit_operator_override(
        tenant_id='tenant-a',
        execution_id='exec-a',
        decision_id='dec-a',
        action_name='publish',
        requested_by='user-a',
        reason='need override',
        subject_fingerprint='fp-a',
    )
    handlers.decide_operator_override(
        override_id=first['override_id'],
        tenant_id='tenant-a',
        actor_id='owner-a',
        role_id=RoleId.OWNER,
        resolution=OperatorOverrideResolution.APPROVE_ONCE,
        note='approved once',
    )
    handlers.submit_operator_override(
        tenant_id='tenant-b',
        execution_id='exec-b',
        decision_id='dec-b',
        action_name='publish',
        requested_by='user-b',
        reason='need override',
        subject_fingerprint='fp-b',
    )

    listing = handlers.list_open_operator_overrides(tenant_id='tenant-a')
    assert listing['count'] == 0
    assert listing['history_count'] == 1
    assert listing['summary']['lifecycle_counts']['approved'] == 1
    assert listing['summary']['resume_candidate_count'] == 1
    assert listing['operator_console']['pending_operator_overrides'] == 0

    tenant_b = handlers.list_open_operator_overrides(tenant_id='tenant-b')
    assert tenant_b['count'] == 1
    assert tenant_b['history_count'] == 1
    assert tenant_b['summary']['lifecycle_counts']['requested'] == 1


from governance.approval_contract import ApprovalOutcome
from governance.approval_store import InMemoryApprovalStore
from governance.control_plane_audit_log import PersistentGovernanceAuditLog


def test_route_handlers_expose_tenant_audit_summary_without_cross_tenant_leak(tmp_path) -> None:
    audit_log = PersistentGovernanceAuditLog(tmp_path / 'audit.jsonl')
    handlers = ApprovalRouteHandlers(
        approval_store=InMemoryApprovalStore(),
        operator_override_store=InMemoryOperatorOverrideStore(),
        audit_log=audit_log,
    )
    approval = handlers.submit_execution_approval(
        tenant_id='tenant-a',
        execution_id='exec-a',
        decision_id='dec-a',
        action_name='send_email',
        requested_by='owner-a',
        reason='need operator review',
        required_role_groups=((RoleId.OWNER,),),
        min_distinct_approvers=1,
        subject_fingerprint='fp-a',
    )
    handlers.decide(
        approval_id=approval['approval_id'],
        tenant_id='tenant-a',
        actor_id='owner-2',
        role_id=RoleId.OWNER,
        outcome=ApprovalOutcome.APPROVE,
        rationale='approved',
    )
    handlers.submit_operator_override(
        tenant_id='tenant-b',
        execution_id='exec-b',
        decision_id='dec-b',
        action_name='publish',
        requested_by='owner-b',
        reason='need one-shot override',
        subject_fingerprint='fp-b',
    )
    listing_a = handlers.list_open(tenant_id='tenant-a')
    assert listing_a['audit']['lifecycle_counts']['approval_requested'] == 1
    assert listing_a['audit']['lifecycle_counts']['approval_decided'] == 1
    assert listing_a['audit']['count'] >= 2
    listing_b = handlers.list_open_operator_overrides(tenant_id='tenant-b')
    assert listing_b['audit']['lifecycle_counts']['override_submitted'] == 1
    assert listing_b['audit']['lifecycle_counts']['approval_requested'] == 0


def test_route_handlers_audit_summary_exposes_integrity(tmp_path) -> None:
    audit_log = PersistentGovernanceAuditLog(tmp_path / 'audit_integrity.jsonl')
    handlers = ApprovalRouteHandlers(
        approval_store=InMemoryApprovalStore(),
        operator_override_store=InMemoryOperatorOverrideStore(),
        audit_log=audit_log,
    )
    handlers.submit_operator_override(
        tenant_id='tenant-a',
        execution_id='exec-integrity',
        decision_id='dec-integrity',
        action_name='publish',
        requested_by='user-a',
        reason='need override',
        subject_fingerprint='fp-integrity',
    )
    listing = handlers.list_open_operator_overrides(tenant_id='tenant-a')
    assert listing['audit']['integrity']['checked'] is True
    assert listing['audit']['integrity']['valid'] is True
    assert listing['audit']['integrity']['event_count'] >= 1



def test_operator_override_listing_uses_recent_history_for_resume_candidates() -> None:
    handlers = ApprovalRouteHandlers(
        approval_store=InMemoryApprovalStore(),
        operator_override_store=InMemoryOperatorOverrideStore(),
    )
    for idx in range(55):
        record = handlers.submit_operator_override(
            tenant_id='tenant-a',
            execution_id=f'exec-{idx}',
            decision_id=f'dec-{idx}',
            action_name='publish',
            requested_by='user-2',
            reason='need override',
            subject_fingerprint=f'fp-{idx}',
        )
        if idx == 54:
            handlers.decide_operator_override(
                override_id=record['override_id'],
                tenant_id='tenant-a',
                actor_id='owner-1',
                role_id=RoleId.OWNER,
                resolution=OperatorOverrideResolution.APPROVE_ONCE,
                note='approved once',
            )
    listing = handlers.list_open_operator_overrides(tenant_id='tenant-a')
    assert listing['summary']['resume_candidate_count'] == 1
    assert listing['resume_candidates'][0]['decision_id'] == 'dec-54'
    assert listing['timeline'][0]['decision_id'] == 'dec-54'

from __future__ import annotations

from governance.approval_store import InMemoryApprovalStore
from governance.rbac_contract import RoleId
from interfaces.api.approval_route_handlers import ApprovalRouteHandlers


def test_execution_submit_and_list_open_summary() -> None:
    handlers = ApprovalRouteHandlers(approval_store=InMemoryApprovalStore())
    record = handlers.submit_execution_approval(
        tenant_id='tenant-a',
        execution_id='exec-1',
        decision_id='dec-1',
        action_name='send_email',
        requested_by='user-1',
        reason='approval required',
        required_role_groups=((RoleId.OWNER,), (RoleId.OPERATOR,)),
        min_distinct_approvers=2,
        subject_fingerprint='fingerprint-1',
    )
    assert record['subject_type'] == 'action_execution'
    assert record['subject_fingerprint'] == 'fingerprint-1'
    listing = handlers.list_open(tenant_id='tenant-a', subject_type='action_execution')
    assert listing['count'] == 1
    assert listing['summary']['execution_pending_count'] == 1
    assert listing['summary']['fingerprint_bound_count'] == 1
    assert listing['summary']['dual_control_count'] == 1


def test_execution_submit_rejects_missing_execution_id() -> None:
    handlers = ApprovalRouteHandlers(approval_store=InMemoryApprovalStore())
    import pytest
    with pytest.raises(ValueError, match='execution_id is required'):
        handlers.submit_execution_approval(
            tenant_id='tenant-a',
            execution_id='',
            decision_id='dec-1',
            action_name='send_email',
            requested_by='user-1',
            reason='approval required',
            required_role_groups=((RoleId.OWNER,),),
            min_distinct_approvers=1,
            subject_fingerprint='fp-1',
        )


def test_execution_list_open_exposes_operator_actions_summary() -> None:
    handlers = ApprovalRouteHandlers(approval_store=InMemoryApprovalStore())
    handlers.submit_execution_approval(
        tenant_id='tenant-a',
        execution_id='exec-1',
        decision_id='dec-1',
        action_name='send_email',
        requested_by='user-1',
        reason='approval required',
        required_role_groups=((RoleId.OWNER,),),
        min_distinct_approvers=1,
        subject_fingerprint='fingerprint-1',
    )
    listing = handlers.list_open(tenant_id='tenant-a', subject_type='action_execution')
    assert listing['operator_console']['action_required'] is True
    assert listing['operator_actions'][0]['decision_id'] == 'dec-1'



def test_execution_list_open_uses_recent_history_for_resume_candidates() -> None:
    handlers = ApprovalRouteHandlers(approval_store=InMemoryApprovalStore())
    for idx in range(55):
        record = handlers.submit_execution_approval(
            tenant_id='tenant-a',
            execution_id=f'exec-{idx}',
            decision_id=f'dec-{idx}',
            action_name='send_email',
            requested_by='user-1',
            reason='approval required',
            required_role_groups=((RoleId.OWNER,),),
            min_distinct_approvers=1,
            subject_fingerprint=f'fp-{idx}',
        )
        if idx == 54:
            handlers.decide(
                approval_id=record['approval_id'],
                tenant_id='tenant-a',
                actor_id='owner-1',
                role_id=RoleId.OWNER,
                outcome=__import__('governance.approval_contract', fromlist=['ApprovalOutcome']).ApprovalOutcome.APPROVE,
                rationale='approved',
            )
    listing = handlers.list_open(tenant_id='tenant-a', subject_type='action_execution')
    assert listing['summary']['resume_candidate_count'] == 1
    assert listing['resume_candidates'][0]['decision_id'] == 'dec-54'
    assert listing['timeline'][0]['decision_id'] == 'dec-54'

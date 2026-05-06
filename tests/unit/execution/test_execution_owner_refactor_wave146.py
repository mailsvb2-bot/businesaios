from contracts.action_impact_contract import ActionExecutionContext, ActionImpact
from execution.approval_gate_fingerprint import build_execution_subject_fingerprint
from execution.business_memory_projection import project_business_memory_feedback_snapshot
from execution.closed_loop_support import build_recovery_summary, normalize_approval_context


def test_business_memory_feedback_snapshot_owner_is_evidence_only() -> None:
    payload = {
        'tenant_id': 'tenant-1',
        'business_id': 'biz-1',
        'business_profile': {'segment': 'services'},
        'active_goals': ['grow'],
        'recent_runs': [{'run_id': 'run-1', 'goal': 'grow', 'status': 'completed'}],
    }
    snapshot = project_business_memory_feedback_snapshot(payload)
    assert snapshot['evidence_only'] is True
    assert snapshot['must_not_issue_decision'] is True


def test_approval_gate_fingerprint_owner_requires_execution_id() -> None:
    ctx = ActionExecutionContext(tenant_id='t-1', user_id='user-1', execution_id='exec-1', action_name='send_email', payload={}, metadata={})
    from contracts.action_impact_contract import ActionCategory
    impact = ActionImpact(action_name='send_email', category=ActionCategory.INTERNAL_WRITE)
    fingerprint = build_execution_subject_fingerprint(ctx=ctx, decision_id='dec-1', impact=impact, external_confirmation_mode='required')
    assert isinstance(fingerprint, str) and fingerprint


def test_closed_loop_support_normalizes_approval_context() -> None:
    normalized = normalize_approval_context(
        action={'tenant_id': 'tenant-1', 'decision_id': 'dec-1'},
        execution_receipt={'tenant_id': 'tenant-1'},
        approval_context={
            'tenant_id': 'tenant-1',
            'decision_id': 'dec-1',
            'execution_id': 'exec-1',
            'approval_id': 'appr-1',
            'subject_fingerprint': 'fp-1',
            'approval_required': True,
        },
    )
    assert normalized['approval_required'] is True
    summary = build_recovery_summary(execution_receipt={'recovery': {'action': 'resume'}}, reliability_trace={'trace_key': 'tr-1'})
    assert summary['action'] == 'resume'

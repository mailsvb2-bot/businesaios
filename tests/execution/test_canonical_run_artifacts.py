from application.headless.models import GoalExecutionStep
from execution.canonical_run_artifacts import (
    canonical_goal_execution_report,
    canonical_goal_execution_step,
    canonical_report_builder_input,
)
from execution.report_builder import ReportBuilder


def test_canonical_step_and_report_artifacts_share_execution_feedback() -> None:
    step = GoalExecutionStep(
        step_index=0,
        decision_id='dec-1',
        action_id='act-1',
        action='telegram.send_message',
        status='executed',
        attempted=True,
        executed=True,
        verified=True,
        operator_required=False,
        correlation_id='corr-1',
        verification_status='verified',
        execution_feedback={
            'action_type': 'telegram.send_message',
            'action_id': 'act-1',
            'decision_id': 'dec-1',
            'correlation_id': 'corr-1',
            'attempted': True,
            'executed': True,
            'verified': True,
            'operator_required': False,
            'verification_status': 'verified',
            'external_refs': ['proof://1'],
        },
    )
    step_artifact = canonical_goal_execution_step(step)
    report_artifact = canonical_goal_execution_report(
        goal='notify users',
        business_id='biz-1',
        tenant_id='tenant-1',
        completed=True,
        stop_reason='goal_reached',
        steps=(step,),
        final_feedback={'execution_feedback': dict(step.execution_feedback)},
    )
    assert step_artifact['execution_feedback']['action_id'] == 'act-1'
    assert report_artifact['execution_feedback']['verification_status'] == 'verified'
    assert report_artifact['step_artifacts'][0]['external_ref'] == 'proof://1'


def test_report_builder_reads_canonical_run_artifact() -> None:
    rendered = ReportBuilder().build(
        record={
            'run_id': 'run-1',
            'goal': 'grow pipeline',
            'business_id': 'biz-1',
            'tenant_id': 'tenant-1',
            'completed': True,
            'stop_reason': 'goal_reached',
            'steps_count': 1,
            'canonical_run_artifact': {
                'verification_status': 'verified',
                'steps_count': 1,
                'execution_feedback': {
                    'attempted': True,
                    'executed': True,
                    'verified': True,
                    'operator_required': False,
                },
                'final_feedback': {'goal_score': 0.9},
            },
        }
    )
    assert 'Steps: 1' in rendered
    assert 'Verification status: verified' in rendered


def test_canonical_report_builder_input_falls_back_to_final_feedback() -> None:
    normalized = canonical_report_builder_input(
        {
            'steps_count': 2,
            'final_feedback': {
                'attempted': True,
                'executed': True,
                'verified': False,
                'verification_status': 'unverified',
            },
        }
    )
    assert normalized['steps_count'] == 2
    assert normalized['execution_feedback']['verification_status'] == 'unverified'

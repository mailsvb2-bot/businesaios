from execution.canonical_persistence_vocabulary import (
    canonical_memory_record,
    canonical_persistence_outcome_record,
    canonical_run_persistence_vocabulary,
)


def test_canonical_run_persistence_vocabulary_prefers_run_artifact_execution_feedback() -> None:
    payload = canonical_run_persistence_vocabulary(
        {
            'run_id': 'run-1',
            'tenant_id': 'tenant-1',
            'business_id': 'biz-1',
            'goal': 'grow revenue',
            'steps_count': 2,
            'final_feedback': {'goal_score': 0.2, 'retry_classification': {'kind': 'operator_required'}},
            'canonical_run_artifact': {
                'verification_status': 'accepted',
                'steps_count': 2,
                'execution_feedback': {
                    'verification_status': 'verified',
                    'verified': True,
                    'executed': True,
                    'external_refs': ['proof://1'],
                },
                'final_feedback': {'goal_score': 0.9},
            },
        }
    )
    assert payload['verification_status'] == 'verified'
    assert payload['verified'] is True
    assert payload['goal_score'] == 0.2
    assert payload['external_refs'] == ['proof://1']


def test_canonical_persistence_outcome_record_embeds_vocabulary() -> None:
    record = canonical_persistence_outcome_record(
        base_record={'tenant_id': 'tenant-1', 'business_id': 'biz-1', 'run_id': 'run-1', 'goal': 'grow'},
        outcome_record={'verification_status': 'accepted', 'executed': True, 'external_refs': ['ref-1']},
    )
    assert record['verification_status'] == 'verified'
    assert record['persistence_vocabulary']['verification_status'] == 'verified'
    assert record['external_refs'] == ['ref-1']


def test_canonical_memory_record_tracks_retry_and_error() -> None:
    record = canonical_memory_record(
        tenant_id='tenant-1',
        business_id='biz-1',
        run_id='run-1',
        goal='grow',
        step_count=3,
        final_feedback={'goal_score': 0.3, 'error': 'timeout', 'retry_classification': {'kind': 'operator_required'}},
        channel='headless',
        region='eu',
        completed=False,
        stop_reason='execution_failed',
    )
    assert record['verification_status'] == 'unverified'
    assert record['persistence_vocabulary']['retry_kind'] == 'operator_required'
    assert record['persistence_vocabulary']['error'] == 'timeout'

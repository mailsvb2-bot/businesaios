from execution.headless_ledger import FileHeadlessLedger, LedgerRecord


def test_ledger_persists_canonical_persistence_vocabulary(tmp_path) -> None:
    ledger = FileHeadlessLedger(root_dir=tmp_path)
    ledger.write(
        LedgerRecord(
            run_id='run-1',
            trace_id='trace-1',
            business_id='biz-1',
            tenant_id='tenant-1',
            goal='grow',
            completed=True,
            stop_reason='goal_reached',
            steps_count=1,
            final_feedback={'goal_score': 0.9, 'retry_classification': {'kind': 'success'}},
            trace={'events': []},
            canonical_run_artifact={'verification_status': 'verified', 'execution_feedback': {'verified': True, 'verification_status': 'verified'}},
        )
    )
    payload = ledger.read('run-1')
    assert payload['canonical_persistence_vocabulary']['verification_status'] == 'verified'
    assert payload['canonical_persistence_vocabulary']['goal_score'] == 0.9

from security.governance_owner_factory import build_security_governance_infrastructure
from security.governance_journal import GovernanceJournalEvent
from security.reencryption_job_store import ReencryptionJob
from security.security_drill_schedule_store import SecurityDrillSchedule


def test_tenant_scoped_security_view_filters_events_jobs_and_drills(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    owner.governance_journal.append(GovernanceJournalEvent(event_kind='tenant.audit', entity_kind='tenant', entity_id='tenant:acme:secret-1', payload={'tenant_id': 'acme'}))
    jobs_path = tmp_path / 'security_reencryption_jobs.sqlite3'
    # store already exists in owner wiring; reopen via module import for explicit put
    from security.reencryption_job_store import SQLiteReencryptionJobStore
    store = SQLiteReencryptionJobStore(str(jobs_path))
    store.put(ReencryptionJob(job_id='job-1', old_key_id='old', new_key_id='new', tenant_id='acme', status='running'))
    drills_path = tmp_path / 'security_drill_schedule.sqlite3'
    from security.security_drill_schedule_store import SQLiteSecurityDrillScheduleStore
    drill_store = SQLiteSecurityDrillScheduleStore(str(drills_path))
    drill_store.put(SecurityDrillSchedule(drill_id='drill-1', drill_kind='token_quarantine_recovery', actor='secops', target_entity_id='tok-1', interval_seconds=60, next_run_epoch_s=0, payload={'tenant_id': 'acme'}))
    view = owner.tenant_isolation.build_view(tenant_id='acme')
    assert len(view.governance_events) >= 1
    assert len(view.reencryption_jobs) == 1
    assert len(view.drill_schedules) == 1

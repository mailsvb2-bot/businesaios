from __future__ import annotations

import pytest

from security.governance_journal import GovernanceJournalEvent, SQLiteGovernanceJournal
from security.reencryption_job_store import ReencryptionJob, SQLiteReencryptionJobStore
from security.security_drill_schedule_store import SQLiteSecurityDrillScheduleStore, SecurityDrillSchedule


def test_storage_level_tenant_filters_do_not_leak_cross_tenant_rows(tmp_path) -> None:
    journal = SQLiteGovernanceJournal(str(tmp_path / 'governance.sqlite3'))
    journal.append(GovernanceJournalEvent(event_kind='tenant.audit', entity_kind='tenant', entity_id='tenant:acme:key-1', payload={'tenant_id': 'acme'}))
    journal.append(GovernanceJournalEvent(event_kind='tenant.audit', entity_kind='tenant', entity_id='tenant:beta:key-2', payload={'tenant_id': 'beta'}))
    assert {item['entity_id'] for item in journal.latest_for_tenant(tenant_id='acme', limit=10)} == {'tenant:acme:key-1'}
    with pytest.raises(PermissionError):
        journal.latest_entity_timeline_for_tenant(tenant_id='acme', entity_kind='tenant', entity_id='tenant:beta:key-2')

    jobs = SQLiteReencryptionJobStore(str(tmp_path / 'jobs.sqlite3'))
    jobs.put(ReencryptionJob(job_id='job-acme', old_key_id='old', new_key_id='new', tenant_id='acme', status='running'))
    jobs.put(ReencryptionJob(job_id='job-beta', old_key_id='old', new_key_id='new', tenant_id='beta', status='running'))
    assert {item.job_id for item in jobs.list_active_for_tenant(tenant_id='acme')} == {'job-acme'}
    with pytest.raises(PermissionError):
        jobs.get_for_tenant(tenant_id='acme', job_id='job-beta')

    drills = SQLiteSecurityDrillScheduleStore(str(tmp_path / 'drills.sqlite3'))
    drills.put(SecurityDrillSchedule(drill_id='drill-acme', drill_kind='tenant', actor='secops', target_entity_id='tenant:acme:key-1', interval_seconds=60, next_run_epoch_s=0, payload={'tenant_id': 'acme'}))
    drills.put(SecurityDrillSchedule(drill_id='drill-beta', drill_kind='tenant', actor='secops', target_entity_id='tenant:beta:key-2', interval_seconds=60, next_run_epoch_s=0, payload={'tenant_id': 'beta'}))
    assert {item.drill_id for item in drills.list_enabled_for_tenant(tenant_id='acme')} == {'drill-acme'}
    with pytest.raises(PermissionError):
        drills.get_for_tenant(tenant_id='acme', drill_id='drill-beta')

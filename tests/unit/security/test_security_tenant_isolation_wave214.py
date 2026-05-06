from __future__ import annotations

import pytest

from security.governance_journal import GovernanceJournalEvent
from security.governance_owner_factory import build_security_governance_infrastructure
from security.reencryption_job_store import ReencryptionJob
from security.security_drill_schedule_store import SecurityDrillSchedule
from security.tenant_security_isolation import TenantSecurityIsolationError


def test_tenant_isolation_build_view_and_direct_access_are_scoped(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    owner.governance_journal.append(GovernanceJournalEvent(event_kind='tenant.audit', entity_kind='tenant', entity_id='tenant:acme:key-1', payload={'tenant_id': 'acme'}))
    owner.governance_journal.append(GovernanceJournalEvent(event_kind='tenant.audit', entity_kind='tenant', entity_id='tenant:beta:key-2', payload={'tenant_id': 'beta'}))
    from security.reencryption_job_store import SQLiteReencryptionJobStore
    jobs = SQLiteReencryptionJobStore(str(tmp_path / 'security_reencryption_jobs.sqlite3'))
    jobs.put(ReencryptionJob(job_id='job-acme', old_key_id='old', new_key_id='new', tenant_id='acme', status='running'))
    jobs.put(ReencryptionJob(job_id='job-beta', old_key_id='old', new_key_id='new', tenant_id='beta', status='running'))
    from security.security_drill_schedule_store import SQLiteSecurityDrillScheduleStore
    drills = SQLiteSecurityDrillScheduleStore(str(tmp_path / 'security_drill_schedule.sqlite3'))
    drills.put(SecurityDrillSchedule(drill_id='drill-acme', drill_kind='x', actor='secops', target_entity_id='tenant:acme:k1', interval_seconds=60, next_run_epoch_s=0, payload={'tenant_id': 'acme'}))
    drills.put(SecurityDrillSchedule(drill_id='drill-beta', drill_kind='x', actor='secops', target_entity_id='tenant:beta:k1', interval_seconds=60, next_run_epoch_s=0, payload={'tenant_id': 'beta'}))

    acme_view = owner.tenant_isolation.build_view(tenant_id='acme')
    assert {item['entity_id'] for item in acme_view.governance_events} == {'tenant:acme:key-1'}
    assert {item.job_id for item in acme_view.reencryption_jobs} == {'job-acme'}
    assert {item.drill_id for item in acme_view.drill_schedules} == {'drill-acme'}
    assert owner.tenant_isolation.get_reencryption_job(tenant_id='acme', job_id='job-acme').job_id == 'job-acme'
    assert owner.tenant_isolation.get_drill_schedule(tenant_id='acme', drill_id='drill-acme').drill_id == 'drill-acme'


def test_tenant_isolation_rejects_cross_tenant_job_drill_and_timeline_access(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    owner.governance_journal.append(GovernanceJournalEvent(event_kind='tenant.audit', entity_kind='tenant', entity_id='tenant:beta:key-2', payload={'tenant_id': 'beta'}))
    from security.reencryption_job_store import SQLiteReencryptionJobStore
    jobs = SQLiteReencryptionJobStore(str(tmp_path / 'security_reencryption_jobs.sqlite3'))
    jobs.put(ReencryptionJob(job_id='job-beta', old_key_id='old', new_key_id='new', tenant_id='beta', status='running'))
    from security.security_drill_schedule_store import SQLiteSecurityDrillScheduleStore
    drills = SQLiteSecurityDrillScheduleStore(str(tmp_path / 'security_drill_schedule.sqlite3'))
    drills.put(SecurityDrillSchedule(drill_id='drill-beta', drill_kind='x', actor='secops', target_entity_id='tenant:beta:k1', interval_seconds=60, next_run_epoch_s=0, payload={'tenant_id': 'beta'}))

    with pytest.raises(TenantSecurityIsolationError):
        owner.tenant_isolation.get_reencryption_job(tenant_id='acme', job_id='job-beta')
    with pytest.raises(TenantSecurityIsolationError):
        owner.tenant_isolation.get_drill_schedule(tenant_id='acme', drill_id='drill-beta')
    with pytest.raises(PermissionError):
        owner.tenant_isolation.latest_entity_timeline(tenant_id='acme', entity_kind='tenant', entity_id='tenant:beta:key-2')

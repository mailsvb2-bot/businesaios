from __future__ import annotations

from security.governance_owner_factory import build_security_governance_infrastructure
from security.reencryption_job_store import ReencryptionJob, SQLiteReencryptionJobStore
from security.security_runtime_summary import SecurityRuntimeSummaryService


def test_security_runtime_summary_reports_core_operational_counts(tmp_path) -> None:
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    owner.governance.quarantine_compromised_token(token_fingerprint='tok-1', actor='secops', reason='drill')
    owner.drill_executor.run_secret_quarantine_recovery_drill(actor='secops', secret_id='secret-1')

    jobs = SQLiteReencryptionJobStore(str(tmp_path / 'reencryption_jobs.sqlite3'))
    jobs.put(ReencryptionJob(job_id='job-1', old_key_id='old', new_key_id='new', status='paused'))

    summary = SecurityRuntimeSummaryService(
        incident_registry=owner.governance._incident_registry,
        quarantine_registry=owner.governance._quarantine_registry,
        reencryption_job_store=jobs,
        drill_history=owner.recovery._drills,
    ).build()

    assert summary.open_incidents >= 1
    assert summary.active_quarantines >= 1
    assert summary.active_reencryption_jobs == 1
    assert summary.paused_reencryption_jobs == 1
    assert summary.latest_drill_ok is True

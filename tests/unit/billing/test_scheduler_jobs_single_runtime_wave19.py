from __future__ import annotations

from billing.scheduler import jobs, jobs_support


def test_jobs_support_is_identity_facade_over_canonical_jobs_runtime() -> None:
    names = (
        "BillingJobRun",
        "BillingJobRunStoreContract",
        "InMemoryBillingJobRunStore",
        "SqliteBillingJobRunStore",
        "_stable_job_fingerprint",
        "_assert_replay_safe",
        "_serialize_reconciliation_report",
        "_deserialize_reconciliation_report",
        "_job_lease_context",
        "_renew_lease_if_due",
    )
    for name in names:
        assert getattr(jobs_support, name) is getattr(jobs, name)
    assert jobs_support.SCHEMA_VERSION == jobs.SCHEMA_VERSION
    assert jobs_support.CANON_BILLING_SCHEDULER_JOBS is True

"""Compatibility facade for the canonical billing scheduler jobs runtime.

This module deliberately owns no job-run storage, reconciliation replay, lease,
or fingerprint implementation. All behavior is provided by ``jobs.py`` and the
canonical platform stores it composes.
"""

from __future__ import annotations

from billing.scheduler.jobs import (
    CANON_BILLING_SCHEDULER_JOBS,
    SCHEMA_VERSION,
    BillingJobRun,
    BillingJobRunStoreContract,
    InMemoryBillingJobRunStore,
    SqliteBillingJobRunStore,
    _assert_replay_safe,
    _deserialize_reconciliation_report,
    _job_lease_context,
    _renew_lease_if_due,
    _serialize_reconciliation_report,
    _stable_job_fingerprint,
)

__all__ = [
    "CANON_BILLING_SCHEDULER_JOBS",
    "SCHEMA_VERSION",
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
]

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from billing.scheduler import jobs

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def test_billing_job_run_validation_and_in_memory_store() -> None:
    run = jobs.BillingJobRun(
        tenant_id="tenant",
        job_name="job",
        run_key="run",
        started_at=NOW,
        finished_at=NOW,
        metadata={"input_fingerprint": "abc"},
    )

    run.validate()

    store = jobs.InMemoryBillingJobRunStore()
    saved = store.save(run)
    assert saved == run
    assert saved is not run
    assert store.get(tenant_id="tenant", job_name="job", run_key="run") == run

    with pytest.raises(ValueError, match="billing job run collision"):
        store.save(jobs.BillingJobRun(tenant_id="tenant", job_name="job", run_key="run", started_at=NOW, metadata={"x": 1}))

    with pytest.raises(ValueError, match="job_name is required"):
        jobs.BillingJobRun(tenant_id="tenant", job_name="", run_key="run", started_at=NOW).validate()

    with pytest.raises(ValueError, match="run_key is required"):
        jobs.BillingJobRun(tenant_id="tenant", job_name="job", run_key="", started_at=NOW).validate()

    with pytest.raises(ValueError, match="started_at must be timezone-aware"):
        jobs.BillingJobRun(tenant_id="tenant", job_name="job", run_key="run", started_at=datetime(2026, 1, 1)).validate()

    with pytest.raises(ValueError, match="finished_at must be >= started_at"):
        jobs.BillingJobRun(tenant_id="tenant", job_name="job", run_key="run", started_at=NOW, finished_at=NOW - timedelta(seconds=1)).validate()


def test_fingerprint_and_replay_safety_guards() -> None:
    assert jobs._stable_job_fingerprint({"b": 2, "a": 1}) == jobs._stable_job_fingerprint({"a": 1, "b": 2})

    fingerprint = jobs._stable_job_fingerprint({"input": 1})
    other_fingerprint = jobs._stable_job_fingerprint({"input": 2})
    existing = jobs.BillingJobRun(
        tenant_id="tenant",
        job_name="job",
        run_key="run",
        started_at=NOW,
        metadata={"input_fingerprint": fingerprint},
    )

    jobs._assert_replay_safe(existing, expected_fingerprint=fingerprint)

    with pytest.raises(ValueError, match="billing job replay input mismatch"):
        jobs._assert_replay_safe(existing, expected_fingerprint=other_fingerprint)


def test_reconciliation_report_serialization_roundtrip() -> None:
    drift = jobs.ReconciliationDrift(
        tenant_id="tenant",
        drift_key="invoice:1",
        expected_minor=100,
        observed_minor=80,
        delta_minor=-20,
        severity="warning",
        details={"invoice_id": "inv-1"},
    )
    report = jobs.ReconciliationReport(tenant_id="tenant", drifts=(drift,))

    payload = jobs._serialize_reconciliation_report(report)
    assert payload[0]["drift_key"] == "invoice:1"

    restored = jobs._deserialize_reconciliation_report(tenant_id="tenant", payload=payload)
    assert restored is not None
    assert restored.drifts[0].delta_minor == -20

    with pytest.raises(ValueError, match="report_drifts"):
        jobs._deserialize_reconciliation_report(tenant_id="tenant", payload={"bad": "shape"})
    with pytest.raises(ValueError, match="report drift"):
        jobs._deserialize_reconciliation_report(tenant_id="tenant", payload=[object()])


@dataclass
class FakeLease:
    fencing_token: str
    expires_at: datetime | None


class FakeLeaseStore:
    def __init__(self) -> None:
        self.acquired: list[object] = []
        self.renewed: list[dict[str, object]] = []
        self.released: list[dict[str, object]] = []

    def acquire(self, lease: object) -> FakeLease:
        self.acquired.append(lease)
        return FakeLease(fencing_token="fence-1", expires_at=NOW + timedelta(seconds=1))

    def renew(self, **kwargs: object) -> FakeLease:
        self.renewed.append(dict(kwargs))
        return FakeLease(fencing_token="fence-2", expires_at=NOW + timedelta(minutes=5))

    def release(self, **kwargs: object) -> None:
        self.released.append(dict(kwargs))


def test_job_lease_context_and_renewal_paths() -> None:
    with jobs._job_lease_context(
        lease_store=None,
        tenant_id="tenant",
        job_name="job",
        run_key="run",
        worker_id="worker",
        observed_at=NOW,
        lease_ttl=timedelta(minutes=5),
    ) as holder:
        assert holder == {"lease": None}

    store = FakeLeaseStore()
    with jobs._job_lease_context(
        lease_store=store,
        tenant_id="tenant",
        job_name="job",
        run_key="run",
        worker_id="worker",
        observed_at=NOW,
        lease_ttl=timedelta(minutes=5),
    ) as holder:
        assert isinstance(holder["lease"], FakeLease)
        jobs._renew_lease_if_due(
            lease_store=store,
            holder=holder,
            tenant_id="tenant",
            job_name="job",
            run_key="run",
            lease_ttl=timedelta(minutes=5),
            now=NOW + timedelta(seconds=2),
        )
        assert isinstance(holder["lease"], FakeLease)

    assert store.acquired
    assert store.renewed
    assert store.released

    with pytest.raises(ValueError, match="now must be timezone-aware"):
        jobs._renew_lease_if_due(
            lease_store=store,
            holder={"lease": FakeLease(fencing_token="x", expires_at=NOW)},
            tenant_id="tenant",
            job_name="job",
            run_key="run",
            lease_ttl=timedelta(minutes=5),
            now=datetime(2026, 1, 1),
        )


@dataclass
class FakeDueAction:
    attempt_no: int


class FakeOrchestrator:
    def __init__(self) -> None:
        self.executed: list[int] = []

    def due_actions(self, **_kwargs: object) -> list[FakeDueAction]:
        return [FakeDueAction(1), FakeDueAction(2)]

    def mark_action_executed(self, **kwargs: object) -> None:
        self.executed.append(int(kwargs["attempt_no"]))


def test_dunning_retry_job_runs_and_replays_existing_result() -> None:
    run_store = jobs.InMemoryBillingJobRunStore()
    orchestrator = FakeOrchestrator()
    job = jobs.DunningRetryJob(orchestrator=orchestrator, run_store=run_store)

    result = job.run(tenant_id="tenant", invoice_id="invoice-1", now=NOW, run_key="retry-1")

    assert result == (1, 2)
    assert orchestrator.executed == [1, 2]

    replay = job.run(tenant_id="tenant", invoice_id="invoice-1", now=NOW, run_key="retry-1")
    assert replay == (1, 2)

    with pytest.raises(ValueError, match="invoice_id is required"):
        job.run(tenant_id="tenant", invoice_id="", now=NOW)

    with pytest.raises(ValueError, match="now must be timezone-aware"):
        job.run(tenant_id="tenant", invoice_id="invoice-1", now=datetime(2026, 1, 1))


class FakeReconciliationService:
    def __init__(self) -> None:
        self.calls = 0

    def reconcile(self, **kwargs: object) -> jobs.ReconciliationReport:
        self.calls += 1
        return jobs.ReconciliationReport(tenant_id=str(kwargs["tenant_id"]), drifts=())


def test_reconciliation_job_runs_and_replays_serialized_report() -> None:
    service = FakeReconciliationService()
    run_store = jobs.InMemoryBillingJobRunStore()
    job = jobs.ReconciliationJob(service=service, run_store=run_store)

    report = job.run(
        tenant_id="tenant",
        invoices=(),
        usage_rollups=(),
        now=NOW,
        run_key="reconcile-1",
    )

    assert report.tenant_id == "tenant"
    assert service.calls == 1

    replay = job.run(
        tenant_id="tenant",
        invoices=(),
        usage_rollups=(),
        now=NOW,
        run_key="reconcile-1",
    )

    assert replay.tenant_id == "tenant"
    assert service.calls == 1

    with pytest.raises(ValueError, match="now must be timezone-aware"):
        job.run(tenant_id="tenant", invoices=(), usage_rollups=(), now=datetime(2026, 1, 1))


def test_job_constructors_reject_non_positive_lease_ttl() -> None:
    with pytest.raises(ValueError, match="lease_ttl must be > 0"):
        jobs.RenewalJob(lease_ttl=timedelta(seconds=0))

    with pytest.raises(ValueError, match="lease_ttl must be > 0"):
        jobs.InvoiceIssueJob(lease_ttl=timedelta(seconds=0))

    with pytest.raises(ValueError, match="lease_ttl must be > 0"):
        jobs.DunningRetryJob(orchestrator=FakeOrchestrator(), lease_ttl=timedelta(seconds=0))

    with pytest.raises(ValueError, match="lease_ttl must be > 0"):
        jobs.ReconciliationJob(service=FakeReconciliationService(), lease_ttl=timedelta(seconds=0))

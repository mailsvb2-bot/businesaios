from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, tzinfo

import pytest

from billing.commercial_cycle_contract import (
    BillingCycleWindow,
    InvoiceLifecycleStatus,
    SubscriptionCommercialEnvelope,
    SubscriptionLifecycleStatus,
)
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.scheduler import jobs

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


class _NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


def _run(**changes) -> jobs.BillingJobRun:
    values = {
        "tenant_id": " tenant-a ",
        "job_name": " renewal ",
        "run_key": " run-1 ",
        "started_at": NOW,
        "finished_at": NOW,
        "metadata": {"nested": {"value": 1}, "ids": ("a", "b")},
    }
    values.update(changes)
    return jobs.BillingJobRun(**values)


def _subscription(*, tenant_id: str = "tenant-a", status=SubscriptionLifecycleStatus.ACTIVE):
    cycle = BillingCycleWindow(
        start_at=NOW - timedelta(days=40),
        end_at=NOW - timedelta(days=10),
        anchor="monthly",
    )
    return SubscriptionCommercialEnvelope(
        tenant_id=tenant_id,
        subscription_id=f"sub-{tenant_id}",
        plan_id="growth",
        status=status,
        cycle=cycle,
        trial_ends_at=(NOW - timedelta(days=20)) if status is SubscriptionLifecycleStatus.TRIALING else None,
        metadata={"nested": {"value": 1}},
    )


def _invoice(*, tenant_id: str = "tenant-a", status=InvoiceLifecycleStatus.DRAFT):
    issued_at = NOW - timedelta(days=1) if status is not InvoiceLifecycleStatus.DRAFT else None
    return CommercialInvoiceEnvelope(
        tenant_id=tenant_id,
        invoice_id=f"inv-{tenant_id}-{status.value}",
        subtotal_minor=100,
        total_minor=100,
        status=status,
        issued_at=issued_at,
        metadata={"nested": {"value": 1}},
    )



def test_renewal_and_invoice_jobs_replay_and_reject_malformed_boundaries() -> None:
    renewal_store = jobs.InMemoryBillingJobRunStore()
    renewal = jobs.RenewalJob(run_store=renewal_store)
    own = _subscription()
    foreign = _subscription(tenant_id="tenant-b")
    result = renewal.run(tenant_id="tenant-a", subscriptions=(own, foreign), now=NOW, run_key="renewal-1")
    assert len(result) == 1
    assert result[0].cycle.start_at == own.cycle.end_at
    replay = renewal.run(tenant_id="tenant-a", subscriptions=(own, foreign), now=NOW, run_key="renewal-1")
    assert replay == result
    with pytest.raises(ValueError, match="replay input mismatch"):
        renewal.run(tenant_id="tenant-a", subscriptions=(), now=NOW, run_key="renewal-1")

    invoice_store = jobs.InMemoryBillingJobRunStore()
    issue = jobs.InvoiceIssueJob(run_store=invoice_store)
    draft = _invoice()
    issued = _invoice(status=InvoiceLifecycleStatus.ISSUED)
    foreign_invoice = _invoice(tenant_id="tenant-b")
    issued_result = issue.run(
        tenant_id="tenant-a",
        invoices=(draft, issued, foreign_invoice),
        issued_at=NOW,
        due_at=NOW + timedelta(days=7),
        run_key="issue-1",
    )
    assert [item.status for item in issued_result] == [InvoiceLifecycleStatus.ISSUED, InvoiceLifecycleStatus.ISSUED]
    assert issue.run(
        tenant_id="tenant-a",
        invoices=(draft, issued, foreign_invoice),
        issued_at=NOW,
        due_at=NOW + timedelta(days=7),
        run_key="issue-1",
    ) == issued_result
    with pytest.raises(ValueError, match="replay input mismatch"):
        issue.run(tenant_id="tenant-a", invoices=(), issued_at=NOW, run_key="issue-1")

    for callable_ in (
        lambda: renewal.run(tenant_id=1, subscriptions=(), now=NOW),
        lambda: renewal.run(tenant_id="tenant-a", subscriptions=(), now=NOW, run_key=" "),
        lambda: issue.run(tenant_id=1, invoices=(), issued_at=NOW),
        lambda: issue.run(tenant_id="tenant-a", invoices=(), issued_at=NOW, run_key=1),
        lambda: jobs.DunningRetryJob(orchestrator=object()).run(
            tenant_id=1, invoice_id="invoice", now=NOW
        ),
    ):
        with pytest.raises(ValueError):
            callable_()


def test_remaining_store_lease_and_job_branches(tmp_path) -> None:
    sqlite_store = jobs.SqliteBillingJobRunStore(sqlite_path=str(tmp_path / "runs.sqlite3"))
    persisted = sqlite_store.save(_run())
    assert persisted == _run().normalized_copy()

    class Lease:
        fencing_token = "fence"
        expires_at = None

    holder = {"lease": None}
    jobs._renew_lease_if_due(
        lease_store=object(),
        holder=holder,
        tenant_id="tenant-a",
        job_name="job",
        run_key="run",
        lease_ttl=timedelta(minutes=5),
        now=NOW,
    )
    jobs._renew_lease_if_due(
        lease_store=object(),
        holder={"lease": Lease()},
        tenant_id="tenant-a",
        job_name="job",
        run_key="run",
        lease_ttl=timedelta(minutes=5),
        now=NOW,
    )

    class FutureLease:
        fencing_token = "fence"
        expires_at = NOW + timedelta(minutes=10)

    jobs._renew_lease_if_due(
        lease_store=object(),
        holder={"lease": FutureLease()},
        tenant_id="tenant-a",
        job_name="job",
        run_key="run",
        lease_ttl=timedelta(minutes=5),
        now=NOW,
    )

    with pytest.raises(ValueError, match="now must be timezone-aware"):
        jobs.RenewalJob().run(
            tenant_id="tenant-a",
            subscriptions=(),
            now=datetime(2026, 1, 1),
        )
    future_cycle = replace(
        _subscription(),
        cycle=BillingCycleWindow(
            start_at=NOW - timedelta(days=1),
            end_at=NOW + timedelta(days=20),
            anchor="monthly",
        ),
    )
    unchanged = jobs.RenewalJob().run(
        tenant_id="tenant-a",
        subscriptions=(future_cycle,),
        now=NOW,
        run_key="future-cycle",
    )
    assert unchanged == (future_cycle,)

    issue = jobs.InvoiceIssueJob()
    with pytest.raises(ValueError, match="issued_at must be timezone-aware"):
        issue.run(tenant_id="tenant-a", invoices=(), issued_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="due_at must be timezone-aware"):
        issue.run(
            tenant_id="tenant-a",
            invoices=(),
            issued_at=NOW,
            due_at=datetime(2026, 1, 2),
        )

    service = type(
        "Service",
        (),
        {
            "calls": 0,
            "reconcile": lambda self, **kwargs: (
                setattr(self, "calls", self.calls + 1)
                or jobs.ReconciliationReport(tenant_id=kwargs["tenant_id"], drifts=())
            ),
        },
    )()
    store = jobs.InMemoryBillingJobRunStore()
    fingerprint = jobs._stable_job_fingerprint(
        {
            "invoices": [],
            "usage": [],
            "revenue_account": "billing.accounts.revenue",
            "usage_rate_minor_by_meter": {},
        }
    )
    store.save(
        jobs.BillingJobRun(
            tenant_id="tenant-a",
            job_name="reconciliation",
            run_key="legacy-report",
            started_at=NOW,
            metadata={"input_fingerprint": fingerprint},
        )
    )
    report = jobs.ReconciliationJob(service=service, run_store=store).run(
        tenant_id="tenant-a",
        invoices=(),
        usage_rollups=(),
        now=NOW,
        run_key="legacy-report",
    )
    assert report.is_clean
    assert service.calls == 1

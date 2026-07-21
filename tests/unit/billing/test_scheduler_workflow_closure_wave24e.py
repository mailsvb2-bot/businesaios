from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, tzinfo
from pathlib import Path

import pytest

from billing.commercial_cycle_contract import (
    BillingCycleWindow,
    InvoiceLifecycleStatus,
    ReconciliationDrift,
    SubscriptionCommercialEnvelope,
    SubscriptionLifecycleStatus,
)
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.reconciliation_service import ReconciliationReport
from billing.scheduler import jobs

NOW = datetime(2026, 2, 1, 12, tzinfo=UTC)


class _NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


def _cycle(*, ended: bool) -> BillingCycleWindow:
    if ended:
        return BillingCycleWindow(
            start_at=NOW - timedelta(days=30),
            end_at=NOW,
            anchor="monthly",
        )
    return BillingCycleWindow(
        start_at=NOW,
        end_at=NOW + timedelta(days=30),
        anchor="monthly",
    )


def _subscription(
    *,
    tenant_id: str = "tenant-a",
    status: SubscriptionLifecycleStatus = SubscriptionLifecycleStatus.ACTIVE,
    ended: bool = True,
    subscription_id: str = "sub-1",
) -> SubscriptionCommercialEnvelope:
    return SubscriptionCommercialEnvelope(
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        plan_id="plan-1",
        status=status,
        cycle=_cycle(ended=ended),
    )


def _invoice(
    *,
    tenant_id: str = "tenant-a",
    status: InvoiceLifecycleStatus = InvoiceLifecycleStatus.DRAFT,
    invoice_id: str = "inv-1",
) -> CommercialInvoiceEnvelope:
    issued_at = None if status is InvoiceLifecycleStatus.DRAFT else NOW - timedelta(days=1)
    return CommercialInvoiceEnvelope(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        currency="USD",
        subtotal_minor=100,
        tax_minor=0,
        total_minor=100,
        status=status,
        issued_at=issued_at,
        due_at=None if issued_at is None else NOW + timedelta(days=7),
    )


class _FalseyRunStore(jobs.InMemoryBillingJobRunStore):
    def __bool__(self) -> bool:
        return False


class _SubscriptionLifecycle:
    def __init__(self) -> None:
        self.renewed: list[str] = []

    def __bool__(self) -> bool:
        return False

    def advance_trial(self, subscription, *, now):
        return subscription

    def suspend_if_expired(self, subscription, *, now):
        return subscription

    def renew_cycle(self, subscription, *, now):
        self.renewed.append(subscription.subscription_id)
        return replace(
            subscription,
            cycle=BillingCycleWindow(
                start_at=subscription.cycle.end_at,
                end_at=subscription.cycle.end_at + timedelta(days=30),
                anchor="monthly",
            ),
        )


class _InvoiceLifecycle:
    def __init__(self) -> None:
        self.issued: list[str] = []

    def __bool__(self) -> bool:
        return False

    def issue(self, invoice, *, issued_at, due_at):
        self.issued.append(invoice.invoice_id)
        return replace(
            invoice,
            status=InvoiceLifecycleStatus.ISSUED,
            issued_at=issued_at,
            due_at=due_at,
        )


class _Service:
    def __init__(self, report: object | None = None) -> None:
        self.calls = 0
        self.report = report

    def reconcile(self, **kwargs):
        self.calls += 1
        if self.report is not None:
            return self.report
        return ReconciliationReport(tenant_id=kwargs["tenant_id"], drifts=())


@dataclass
class _Action:
    attempt_no: object


class _Orchestrator:
    def __init__(self, attempts: tuple[object, ...] = ()) -> None:
        self.attempts = attempts
        self.executed: list[object] = []

    def due_actions(self, **_kwargs: object) -> tuple[_Action, ...]:
        return tuple(_Action(value) for value in self.attempts)

    def mark_action_executed(self, **kwargs: object) -> None:
        self.executed.append(kwargs["attempt_no"])


@dataclass
class _Lease:
    fencing_token: str = "fence"
    expires_at: datetime | None = None


class _LeaseStore:
    def __init__(self) -> None:
        self.renewed = 0

    def renew(self, **_kwargs: object) -> _Lease:
        self.renewed += 1
        return _Lease(fencing_token="new", expires_at=NOW + timedelta(minutes=5))


def test_remaining_value_store_and_replay_guards(tmp_path: Path) -> None:
    run = jobs.BillingJobRun(
        tenant_id="tenant-a",
        job_name="job",
        run_key="run",
        started_at=NOW,
    )
    with pytest.raises(ValueError, match="metadata must be a mapping"):
        replace(run, metadata=[]).validate()

    store = jobs.InMemoryBillingJobRunStore()
    with pytest.raises(ValueError, match="run must be a BillingJobRun"):
        store.save(object())
    first = store.save(run)
    second = store.save(run)
    assert first == second
    assert first is not second

    assert jobs.BillingJobRunStoreContract.save(object(), run) is None
    assert (
        jobs.BillingJobRunStoreContract.get(
            object(),
            tenant_id="tenant-a",
            job_name="job",
            run_key="run",
        )
        is None
    )

    sqlite_store = jobs.SqliteBillingJobRunStore(
        sqlite_path=str(tmp_path / "scheduler-runs.sqlite3")
    )
    assert sqlite_store.save(run) == run
    assert (
        sqlite_store.get(
            tenant_id="tenant-a",
            job_name="job",
            run_key="run",
        )
        == run
    )

    with pytest.raises(ValueError, match="lowercase SHA-256"):
        jobs._require_fingerprint("fingerprint", "A" * 64)

    expected = jobs._stable_job_fingerprint({"expected": 1})
    actual = jobs._stable_job_fingerprint({"actual": 1})
    existing = jobs.BillingJobRun(
        tenant_id="tenant-a",
        job_name="job",
        run_key="result-compatible",
        started_at=NOW,
        metadata={
            "input_fingerprint": actual,
            "result_fingerprint": expected,
        },
    )
    jobs._assert_replay_safe(existing, expected_fingerprint=expected)


def test_remaining_reconciliation_serialization_guards() -> None:
    with pytest.raises(ValueError, match="report must be"):
        jobs._serialize_reconciliation_report(object())

    invalid_drift_report = ReconciliationReport(
        tenant_id="tenant-a",
        drifts=(object(),),
    )
    with pytest.raises(ValueError, match="report drifts"):
        jobs._serialize_reconciliation_report(invalid_drift_report)

    cross_tenant = ReconciliationDrift(
        tenant_id="tenant-b",
        drift_key="invoice:1",
        expected_minor=100,
        observed_minor=90,
        delta_minor=-10,
        severity="warning",
    )
    with pytest.raises(ValueError, match="tenant mismatch"):
        jobs._serialize_reconciliation_report(
            ReconciliationReport(tenant_id="tenant-a", drifts=(cross_tenant,))
        )

    with pytest.raises(ValueError, match="tenant mismatch"):
        jobs._deserialize_reconciliation_report(
            tenant_id="tenant-a",
            payload=(
                {
                    "tenant_id": "tenant-b",
                    "drift_key": "invoice:1",
                    "expected_minor": 100,
                    "observed_minor": 90,
                    "delta_minor": -10,
                    "severity": "warning",
                },
            ),
        )


def test_lease_nonrenewal_and_false_awareness_paths() -> None:
    store = _LeaseStore()
    common = {
        "lease_store": store,
        "tenant_id": "tenant-a",
        "job_name": "job",
        "run_key": "run",
        "lease_ttl": timedelta(minutes=5),
        "now": NOW,
    }
    jobs._renew_lease_if_due(holder={"lease": None}, **common)
    jobs._renew_lease_if_due(holder={"lease": _Lease(expires_at=None)}, **common)
    jobs._renew_lease_if_due(
        holder={"lease": _Lease(expires_at=NOW + timedelta(minutes=3))},
        **common,
    )
    assert store.renewed == 0

    false_aware = datetime(2026, 2, 1, tzinfo=_NoOffset())
    with pytest.raises(ValueError, match="now must be timezone-aware"):
        jobs._renew_lease_if_due(
            lease_store=store,
            holder={"lease": _Lease(expires_at=NOW)},
            tenant_id="tenant-a",
            job_name="job",
            run_key="run",
            lease_ttl=timedelta(minutes=5),
            now=false_aware,
        )


def test_falsey_dependencies_are_preserved_by_identity() -> None:
    run_store = _FalseyRunStore()
    subscription_lifecycle = _SubscriptionLifecycle()
    invoice_lifecycle = _InvoiceLifecycle()
    orchestrator = _Orchestrator()
    service = _Service()

    renewal = jobs.RenewalJob(
        lifecycle=subscription_lifecycle,
        run_store=run_store,
    )
    invoice = jobs.InvoiceIssueJob(
        lifecycle=invoice_lifecycle,
        run_store=run_store,
    )
    dunning = jobs.DunningRetryJob(
        orchestrator=orchestrator,
        run_store=run_store,
    )
    reconciliation = jobs.ReconciliationJob(
        service=service,
        run_store=run_store,
    )

    assert renewal._lifecycle is subscription_lifecycle
    assert renewal._run_store is run_store
    assert invoice._lifecycle is invoice_lifecycle
    assert invoice._run_store is run_store
    assert dunning._run_store is run_store
    assert reconciliation._run_store is run_store


def test_renewal_and_invoice_workflows_cover_filter_transition_and_replay() -> None:
    subscription_lifecycle = _SubscriptionLifecycle()
    renewal_store = jobs.InMemoryBillingJobRunStore()
    renewal = jobs.RenewalJob(
        lifecycle=subscription_lifecycle,
        run_store=renewal_store,
    )
    subscriptions = (
        _subscription(subscription_id="renew", ended=True),
        _subscription(
            subscription_id="keep",
            status=SubscriptionLifecycleStatus.SUSPENDED,
            ended=False,
        ),
        _subscription(
            tenant_id="tenant-b",
            subscription_id="other",
            ended=True,
        ),
    )
    result = renewal.run(
        tenant_id="tenant-a",
        subscriptions=subscriptions,
        now=NOW,
        run_key="renewal-1",
    )
    assert [item.subscription_id for item in result] == ["renew", "keep"]
    assert subscription_lifecycle.renewed == ["renew"]

    replay = renewal.run(
        tenant_id="tenant-a",
        subscriptions=subscriptions,
        now=NOW + timedelta(days=1),
        run_key="renewal-1",
    )
    assert [item.subscription_id for item in replay] == ["renew", "keep"]
    assert subscription_lifecycle.renewed == ["renew", "renew"]

    invoice_lifecycle = _InvoiceLifecycle()
    invoice_store = jobs.InMemoryBillingJobRunStore()
    invoice_job = jobs.InvoiceIssueJob(
        lifecycle=invoice_lifecycle,
        run_store=invoice_store,
    )
    invoices = (
        _invoice(invoice_id="draft", status=InvoiceLifecycleStatus.DRAFT),
        _invoice(invoice_id="issued", status=InvoiceLifecycleStatus.ISSUED),
        _invoice(
            tenant_id="tenant-b",
            invoice_id="other",
            status=InvoiceLifecycleStatus.DRAFT,
        ),
    )
    due_at = NOW + timedelta(days=7)
    issued = invoice_job.run(
        tenant_id="tenant-a",
        invoices=invoices,
        issued_at=NOW,
        due_at=due_at,
        run_key="issue-1",
    )
    assert [item.invoice_id for item in issued] == ["draft", "issued"]
    assert invoice_lifecycle.issued == ["draft"]

    replayed = invoice_job.run(
        tenant_id="tenant-a",
        invoices=invoices,
        issued_at=NOW + timedelta(days=1),
        due_at=due_at,
        run_key="issue-1",
    )
    assert [item.invoice_id for item in replayed] == ["draft", "issued"]
    assert invoice_lifecycle.issued == ["draft", "draft"]


def test_dunning_replay_binding_and_pre_effect_validation() -> None:
    store = jobs.InMemoryBillingJobRunStore()
    store.save(
        jobs.BillingJobRun(
            tenant_id="tenant-a",
            job_name="dunning_retry",
            run_key="shared-key",
            started_at=NOW,
            finished_at=NOW,
            metadata={
                "invoice_id": "invoice-a",
                "executed_attempts": (1,),
            },
        )
    )
    with pytest.raises(ValueError, match="invoice mismatch"):
        jobs.DunningRetryJob(
            orchestrator=_Orchestrator(),
            run_store=store,
        ).run(
            tenant_id="tenant-a",
            invoice_id="invoice-b",
            now=NOW,
            run_key="shared-key",
        )

    for attempts in ((1, "2"), (1, 1)):
        orchestrator = _Orchestrator(attempts)
        with pytest.raises(ValueError):
            jobs.DunningRetryJob(orchestrator=orchestrator).run(
                tenant_id="tenant-a",
                invoice_id="invoice-a",
                now=NOW,
                run_key=f"invalid-{attempts!r}",
            )
        assert orchestrator.executed == []

    empty = _Orchestrator()
    assert jobs.DunningRetryJob(orchestrator=empty).run(
        tenant_id="tenant-a",
        invoice_id="invoice-a",
        now=NOW,
        run_key="empty",
    ) == ()
    assert empty.executed == []


def test_reconciliation_legacy_replay_and_invalid_service_results() -> None:
    fingerprint = jobs._stable_job_fingerprint(
        {
            "invoices": [],
            "usage": [],
            "revenue_account": "billing.accounts.revenue",
            "usage_rate_minor_by_meter": {},
        }
    )
    legacy_store = jobs.InMemoryBillingJobRunStore()
    legacy_store.save(
        jobs.BillingJobRun(
            tenant_id="tenant-a",
            job_name="reconciliation",
            run_key="legacy",
            started_at=NOW,
            finished_at=NOW,
            metadata={"input_fingerprint": fingerprint},
        )
    )
    service = _Service()
    report = jobs.ReconciliationJob(
        service=service,
        run_store=legacy_store,
    ).run(
        tenant_id="tenant-a",
        invoices=(),
        usage_rollups=(),
        now=NOW,
        run_key="legacy",
    )
    assert report.tenant_id == "tenant-a"
    assert service.calls == 1

    for invalid_report in (
        object(),
        ReconciliationReport(tenant_id="tenant-b", drifts=()),
    ):
        invalid_service = _Service(invalid_report)
        with pytest.raises(ValueError, match="invalid tenant report"):
            jobs.ReconciliationJob(service=invalid_service).run(
                tenant_id="tenant-a",
                invoices=(),
                usage_rollups=(),
                now=NOW,
                run_key=f"invalid-{type(invalid_report).__name__}",
            )

        invalid_legacy_store = jobs.InMemoryBillingJobRunStore()
        invalid_legacy_store.save(
            jobs.BillingJobRun(
                tenant_id="tenant-a",
                job_name="reconciliation",
                run_key="invalid-legacy",
                started_at=NOW,
                finished_at=NOW,
                metadata={"input_fingerprint": fingerprint},
            )
        )
        with pytest.raises(ValueError, match="invalid tenant report"):
            jobs.ReconciliationJob(
                service=invalid_service,
                run_store=invalid_legacy_store,
            ).run(
                tenant_id="tenant-a",
                invoices=(),
                usage_rollups=(),
                now=NOW,
                run_key="invalid-legacy",
            )

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo

import pytest

from billing.scheduler.jobs import (
    BillingJobRun,
    DunningRetryJob,
    InMemoryBillingJobRunStore,
    InvoiceIssueJob,
    ReconciliationJob,
    RenewalJob,
    _require_attempt_history,
    _require_attempt_number,
    _resolve_run_key,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


@dataclass
class _Action:
    attempt_no: object


class _Orchestrator:
    def __init__(self, attempts: tuple[object, ...] = ()) -> None:
        self._attempts = attempts
        self.executed: list[object] = []

    def due_actions(self, **_kwargs: object) -> tuple[_Action, ...]:
        return tuple(_Action(value) for value in self._attempts)

    def mark_action_executed(self, **kwargs: object) -> None:
        self.executed.append(kwargs["attempt_no"])


class _ReconciliationService:
    def reconcile(self, **kwargs: object):
        from billing.reconciliation_service import ReconciliationReport

        return ReconciliationReport(tenant_id=kwargs["tenant_id"], drifts=())


def test_run_key_and_attempt_boundaries_are_exact() -> None:
    assert _resolve_run_key(None, default=" default ") == "default"
    assert _resolve_run_key(" explicit ", default="unused") == "explicit"
    for value in ("", " ", 0, False, object()):
        with pytest.raises(ValueError):
            _resolve_run_key(value, default="fallback")

    assert _require_attempt_number(1) == 1
    for value in (0, -1, True, 1.0, "1"):
        with pytest.raises(ValueError):
            _require_attempt_number(value)

    assert _require_attempt_history([1, 2]) == (1, 2)
    assert _require_attempt_history((3,)) == (3,)
    for value in (None, {1, 2}, "12", [1, 1], [True], ["1"]):
        with pytest.raises(ValueError):
            _require_attempt_history(value)


def test_all_scheduler_workflows_reject_coercible_ids_keys_and_false_awareness() -> None:
    renewal = RenewalJob()
    invoice = InvoiceIssueJob()
    dunning = DunningRetryJob(orchestrator=_Orchestrator())
    reconciliation = ReconciliationJob(service=_ReconciliationService())

    for tenant_id in (1, False, None):
        with pytest.raises(ValueError):
            renewal.run(tenant_id=tenant_id, subscriptions=(), now=NOW)
        with pytest.raises(ValueError):
            invoice.run(tenant_id=tenant_id, invoices=(), issued_at=NOW)
        with pytest.raises(ValueError):
            dunning.run(tenant_id=tenant_id, invoice_id="invoice-1", now=NOW)
        with pytest.raises(ValueError):
            reconciliation.run(tenant_id=tenant_id, invoices=(), usage_rollups=(), now=NOW)

    for run_key in (0, False, " "):
        with pytest.raises(ValueError):
            renewal.run(tenant_id="tenant-a", subscriptions=(), now=NOW, run_key=run_key)
        with pytest.raises(ValueError):
            invoice.run(tenant_id="tenant-a", invoices=(), issued_at=NOW, run_key=run_key)
        with pytest.raises(ValueError):
            dunning.run(tenant_id="tenant-a", invoice_id="invoice-1", now=NOW, run_key=run_key)
        with pytest.raises(ValueError):
            reconciliation.run(
                tenant_id="tenant-a",
                invoices=(),
                usage_rollups=(),
                now=NOW,
                run_key=run_key,
            )

    for invoice_id in (1, False, None, " "):
        with pytest.raises(ValueError):
            dunning.run(tenant_id="tenant-a", invoice_id=invoice_id, now=NOW)

    false_aware = datetime(2026, 1, 1, tzinfo=_NoOffset())
    with pytest.raises(ValueError, match="now must be timezone-aware"):
        renewal.run(tenant_id="tenant-a", subscriptions=(), now=false_aware)
    with pytest.raises(ValueError, match="issued_at must be timezone-aware"):
        invoice.run(tenant_id="tenant-a", invoices=(), issued_at=false_aware)
    with pytest.raises(ValueError, match="due_at must be timezone-aware"):
        invoice.run(tenant_id="tenant-a", invoices=(), issued_at=NOW, due_at=false_aware)
    with pytest.raises(ValueError, match="now must be timezone-aware"):
        dunning.run(tenant_id="tenant-a", invoice_id="invoice-1", now=false_aware)
    with pytest.raises(ValueError, match="now must be timezone-aware"):
        reconciliation.run(tenant_id="tenant-a", invoices=(), usage_rollups=(), now=false_aware)


def test_dunning_replay_and_new_actions_reject_coercible_attempt_numbers() -> None:
    for history in (["1"], [True], [1, 1], "1"):
        store = InMemoryBillingJobRunStore()
        store.save(
            BillingJobRun(
                tenant_id="tenant-a",
                job_name="dunning_retry",
                run_key="retry-1",
                started_at=NOW,
                finished_at=NOW,
                metadata={"executed_attempts": history},
            )
        )
        job = DunningRetryJob(orchestrator=_Orchestrator(), run_store=store)
        with pytest.raises(ValueError):
            job.run(
                tenant_id="tenant-a",
                invoice_id="invoice-1",
                now=NOW,
                run_key="retry-1",
            )

    for attempt in (True, 0, -1, "1", 1.0):
        job = DunningRetryJob(orchestrator=_Orchestrator((attempt,)))
        with pytest.raises(ValueError):
            job.run(tenant_id="tenant-a", invoice_id="invoice-1", now=NOW, run_key="new")

    orchestrator = _Orchestrator((1, 2))
    assert DunningRetryJob(orchestrator=orchestrator).run(
        tenant_id="tenant-a",
        invoice_id="invoice-1",
        now=NOW,
        run_key="valid",
    ) == (1, 2)
    assert orchestrator.executed == [1, 2]

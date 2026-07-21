from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from billing.commercial_cycle_contract import ReconciliationDrift
from billing.scheduler import jobs

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

def test_reconciliation_report_replay_is_tenant_and_type_strict() -> None:
    drift = ReconciliationDrift(
        tenant_id="tenant-a",
        drift_key="invoice:1",
        expected_minor=100,
        observed_minor=80,
        delta_minor=-20,
        severity="warning",
        details={"nested": {"value": 1}},
    )
    payload = jobs._serialize_reconciliation_report(jobs.ReconciliationReport("tenant-a", (drift,)))
    restored = jobs._deserialize_reconciliation_report(tenant_id=" tenant-a ", payload=payload)
    assert restored == jobs.ReconciliationReport("tenant-a", (drift,))
    payload[0]["details"]["nested"]["value"] = 9
    assert drift.details["nested"]["value"] == 1

    assert jobs._deserialize_reconciliation_report(tenant_id="tenant-a", payload={}) is None
    assert jobs._deserialize_reconciliation_report(tenant_id="tenant-a", payload=[object()]) is None
    invalid_payloads = [
        [{**payload[0], "tenant_id": "tenant-b"}],
        [{**payload[0], "expected_minor": "100"}],
        [{**payload[0], "delta_minor": -19}],
        [{**payload[0], "details": []}],
        [{**payload[0], "drift_key": " "}],
    ]
    for invalid in invalid_payloads:
        with pytest.raises(ValueError):
            jobs._deserialize_reconciliation_report(tenant_id="tenant-a", payload=invalid)

    with pytest.raises(ValueError, match="tenant mismatch"):
        jobs._serialize_reconciliation_report(
            jobs.ReconciliationReport("tenant-a", (replace(drift, tenant_id="tenant-b"),))
        )
    with pytest.raises(ValueError, match="tuple"):
        jobs._serialize_reconciliation_report(jobs.ReconciliationReport("tenant-a", [drift]))
    with pytest.raises(ValueError, match="ReconciliationDrift"):
        jobs._serialize_reconciliation_report(jobs.ReconciliationReport("tenant-a", (object(),)))


def test_run_keys_attempts_and_dunning_replay_are_strict() -> None:
    assert jobs._require_run_key(None, default=" default ") == "default"
    for value in (1, " "):
        with pytest.raises(ValueError):
            jobs._require_run_key(value, default="default")
    assert jobs._require_attempts([1, 2]) == (1, 2)
    for payload in ("1", [True], ["1"], [0], [1, 1]):
        with pytest.raises(ValueError):
            jobs._require_attempts(payload)

    class Orchestrator:
        def __init__(self) -> None:
            self.executed = []

        def due_actions(self, **kwargs):
            return [type("Action", (), {"attempt_no": 1})()]

        def mark_action_executed(self, **kwargs):
            self.executed.append(kwargs["attempt_no"])

    store = jobs.InMemoryBillingJobRunStore()
    orchestrator = Orchestrator()
    job = jobs.DunningRetryJob(orchestrator=orchestrator, run_store=store)
    assert job.run(tenant_id="tenant-a", invoice_id="invoice-1", now=NOW, run_key="retry") == (1,)
    assert job.run(tenant_id="tenant-a", invoice_id="invoice-1", now=NOW, run_key="retry") == (1,)
    assert orchestrator.executed == [1]

    legacy_store = jobs.InMemoryBillingJobRunStore()
    legacy_store.save(
        jobs.BillingJobRun(
            tenant_id="tenant-a",
            job_name="dunning_retry",
            run_key="legacy",
            started_at=NOW,
            metadata={"invoice_id": "invoice-1", "executed_attempts": [1, 2]},
        )
    )
    legacy = jobs.DunningRetryJob(orchestrator=orchestrator, run_store=legacy_store)
    assert legacy.run(tenant_id="tenant-a", invoice_id="invoice-1", now=NOW, run_key="legacy") == (1, 2)
    with pytest.raises(ValueError, match="replay input mismatch"):
        legacy.run(tenant_id="tenant-a", invoice_id="invoice-2", now=NOW, run_key="legacy")


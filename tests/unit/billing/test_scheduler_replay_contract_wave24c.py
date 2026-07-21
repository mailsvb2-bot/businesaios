from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from math import nan

import pytest

from billing.commercial_cycle_contract import ReconciliationDrift
from billing.reconciliation_service import ReconciliationReport
from billing.scheduler.jobs import (
    BillingJobRun,
    _assert_replay_safe,
    _deserialize_reconciliation_report,
    _serialize_reconciliation_report,
    _stable_job_fingerprint,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _fingerprint(value: object) -> str:
    return _stable_job_fingerprint(value)


def _run(**changes) -> BillingJobRun:
    values = {
        "tenant_id": "tenant-a",
        "job_name": "renewal",
        "run_key": "run-1",
        "started_at": NOW,
        "finished_at": NOW,
        "metadata": {"input_fingerprint": _fingerprint({"input": 1})},
    }
    values.update(changes)
    return BillingJobRun(**values)


def _drift(**changes) -> ReconciliationDrift:
    values = {
        "tenant_id": "tenant-a",
        "drift_key": "ledger_total",
        "expected_minor": 100,
        "observed_minor": 120,
        "delta_minor": 20,
        "severity": "high",
        "details": {"ids": ("a", "b")},
    }
    values.update(changes)
    return ReconciliationDrift(**values)


def test_fingerprint_is_json_canonical_and_rejects_coercion() -> None:
    assert _fingerprint({"b": 2, "a": (1, 2)}) == _fingerprint({"a": [1, 2], "b": 2})
    assert _fingerprint({"text": "Привет"}) == _fingerprint({"text": "Привет"})
    for payload in ({"bad": {1}}, {"bad": nan}, {1: "value"}, {"a": 1, " a ": 2}):
        with pytest.raises(ValueError):
            _fingerprint(payload)


def test_replay_fingerprint_fails_closed_and_allows_explicit_result_compatibility() -> None:
    expected = _fingerprint({"input": 1})
    accepted = _fingerprint({"legacy": 1})
    _assert_replay_safe(_run(), expected_fingerprint=expected)
    _assert_replay_safe(
        _run(metadata={"input_fingerprint": _fingerprint({"other": 1}), "result_fingerprint": accepted}),
        expected_fingerprint=expected,
        accepted_fingerprints=(accepted,),
    )

    invalid = [
        (_run(metadata={}), expected, ()),
        (_run(metadata={"input_fingerprint": 1}), expected, ()),
        (_run(metadata={"input_fingerprint": "bad"}), expected, ()),
        (_run(metadata={"input_fingerprint": _fingerprint({"other": 1})}), expected, ()),
        (_run(), "bad", ()),
        (_run(), expected, ("bad",)),
    ]
    for run, fingerprint, accepted_fingerprints in invalid:
        with pytest.raises(ValueError):
            _assert_replay_safe(
                run,
                expected_fingerprint=fingerprint,
                accepted_fingerprints=accepted_fingerprints,
            )


def test_reconciliation_report_round_trip_is_strict_and_tenant_safe() -> None:
    report = ReconciliationReport(tenant_id="tenant-a", drifts=(_drift(),))
    payload = _serialize_reconciliation_report(report)
    assert payload[0]["details"] == {"ids": ["a", "b"]}
    restored = _deserialize_reconciliation_report(tenant_id=" tenant-a ", payload=payload)
    assert restored == ReconciliationReport(
        tenant_id="tenant-a",
        drifts=(replace(_drift(), details={"ids": ["a", "b"]}),),
    )
    assert _deserialize_reconciliation_report(tenant_id="tenant-a", payload=None) is None

    invalid_reports = [
        object(),
        ReconciliationReport(tenant_id="tenant-a", drifts=(object(),)),
        ReconciliationReport(tenant_id="tenant-a", drifts=(_drift(tenant_id="tenant-b"),)),
    ]
    for invalid in invalid_reports:
        with pytest.raises(ValueError):
            _serialize_reconciliation_report(invalid)

    malformed = [
        {},
        [object()],
        [{**payload[0], "tenant_id": "tenant-b"}],
        [{**payload[0], "expected_minor": "100"}],
        [{**payload[0], "expected_minor": True}],
        [{**payload[0], "details": {"bad": {1}}}],
        [{**payload[0], "delta_minor": 21}],
    ]
    for value in malformed:
        with pytest.raises(ValueError):
            _deserialize_reconciliation_report(tenant_id="tenant-a", payload=value)

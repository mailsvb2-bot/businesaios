from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, tzinfo
from threading import Thread

import pytest

from billing.scheduler.jobs import BillingJobRun, InMemoryBillingJobRunStore

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


def _run(**changes) -> BillingJobRun:
    values = {
        "tenant_id": " tenant-a ",
        "job_name": " renewal ",
        "run_key": " run-1 ",
        "started_at": NOW,
        "finished_at": NOW,
        "metadata": {"nested": {"value": 1}, "ids": ("a", "b")},
    }
    values.update(changes)
    return BillingJobRun(**values)


def test_run_contract_normalizes_deeply_and_fails_closed() -> None:
    source = _run()
    normalized = source.normalized_copy()
    assert normalized.tenant_id == "tenant-a"
    assert normalized.job_name == "renewal"
    assert normalized.run_key == "run-1"
    assert normalized.metadata["ids"] == ["a", "b"]
    normalized.metadata["nested"]["value"] = 9
    assert source.metadata["nested"]["value"] == 1
    assert _run(finished_at=None).normalized_copy().finished_at is None

    invalid = [
        _run(tenant_id=1),
        _run(tenant_id=" "),
        _run(job_name=1),
        _run(job_name=" "),
        _run(run_key=1),
        _run(run_key=" "),
        _run(started_at=datetime(2026, 1, 1)),
        _run(started_at=datetime(2026, 1, 1, tzinfo=_NoOffset())),
        _run(finished_at=datetime(2026, 1, 1)),
        _run(finished_at=datetime(2025, 1, 1, tzinfo=UTC)),
        _run(metadata=[]),
        _run(metadata={"bad": {1}}),
        _run(metadata={"bad": float("nan")}),
        _run(metadata={1: "value"}),
        _run(metadata={"a": 1, " a ": 2}),
    ]
    for run in invalid:
        with pytest.raises(ValueError):
            run.validate()


def test_in_memory_store_is_snapshot_safe_idempotent_and_collision_strict() -> None:
    store = InMemoryBillingJobRunStore()
    source = _run()
    saved = store.save(source)
    assert store.save(source) == saved
    saved.metadata["nested"]["value"] = 99
    fetched = store.get(tenant_id=" tenant-a ", job_name=" renewal ", run_key=" run-1 ")
    assert fetched is not None
    assert fetched.metadata["nested"]["value"] == 1
    assert store.get(tenant_id="tenant-a", job_name="renewal", run_key="missing") is None
    with pytest.raises(ValueError, match="collision"):
        store.save(replace(source, metadata={"different": True}))
    with pytest.raises(ValueError, match="BillingJobRun"):
        store.save(object())
    for kwargs in (
        {"tenant_id": 1, "job_name": "renewal", "run_key": "run-1"},
        {"tenant_id": "tenant-a", "job_name": 1, "run_key": "run-1"},
        {"tenant_id": "tenant-a", "job_name": "renewal", "run_key": 1},
    ):
        with pytest.raises(ValueError):
            store.get(**kwargs)


def test_in_memory_store_has_one_winner_under_concurrent_idempotent_save() -> None:
    store = InMemoryBillingJobRunStore()
    results: list[BillingJobRun] = []
    errors: list[BaseException] = []

    def save() -> None:
        try:
            results.append(store.save(_run()))
        except BaseException as exc:
            errors.append(exc)

    threads = [Thread(target=save) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(results) == 20
    assert all(result == results[0] for result in results)

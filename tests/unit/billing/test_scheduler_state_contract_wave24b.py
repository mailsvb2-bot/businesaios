from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta, tzinfo

import pytest

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



def test_run_contract_normalizes_deeply_and_rejects_coercion() -> None:
    source = _run()
    normalized = source.normalized_copy()
    assert normalized.tenant_id == "tenant-a"
    assert normalized.job_name == "renewal"
    assert normalized.run_key == "run-1"
    assert normalized.metadata == {"ids": ["a", "b"], "nested": {"value": 1}}
    normalized.metadata["nested"]["value"] = 9
    assert source.metadata["nested"]["value"] == 1

    invalid = [
        _run(tenant_id=1),
        _run(job_name=1),
        _run(job_name=" "),
        _run(run_key=1),
        _run(run_key=" "),
        _run(started_at="2026-01-01"),
        _run(started_at=datetime(2026, 1, 1, tzinfo=_NoOffset())),
        _run(finished_at=datetime(2026, 1, 1)),
        _run(finished_at=NOW - timedelta(seconds=1)),
        _run(metadata=[]),
        _run(metadata={"bad": float("inf")}),
    ]
    for run in invalid:
        with pytest.raises(ValueError):
            run.validate()


def test_in_memory_store_is_thread_safe_idempotent_and_defensive() -> None:
    store = jobs.InMemoryBillingJobRunStore()
    source = _run()
    with ThreadPoolExecutor(max_workers=8) as pool:
        returned = list(pool.map(store.save, [source] * 32))
    assert all(item is source for item in returned)

    source.metadata["nested"]["value"] = 99
    fetched = store.get(tenant_id=" tenant-a ", job_name=" renewal ", run_key=" run-1 ")
    assert fetched is not None
    assert fetched.metadata["nested"]["value"] == 1
    fetched.metadata["nested"]["value"] = 77
    assert store.get(tenant_id="tenant-a", job_name="renewal", run_key="run-1").metadata["nested"]["value"] == 1

    with pytest.raises(ValueError, match="collision"):
        store.save(replace(_run(), metadata={"different": True}))
    for kwargs in (
        {"tenant_id": 1, "job_name": "renewal", "run_key": "run-1"},
        {"tenant_id": "tenant-a", "job_name": 1, "run_key": "run-1"},
        {"tenant_id": "tenant-a", "job_name": "renewal", "run_key": 1},
    ):
        with pytest.raises(ValueError):
            store.get(**kwargs)


def test_fingerprints_are_json_canonical_and_replay_is_fail_closed() -> None:
    fingerprint = jobs._stable_job_fingerprint({"ids": (1, 2), "nested": {"b": 2, "a": 1}})
    assert fingerprint == jobs._stable_job_fingerprint({"nested": {"a": 1, "b": 2}, "ids": [1, 2]})
    for payload in ({"bad": {1}}, {"bad": float("nan")}, object()):
        with pytest.raises(ValueError):
            jobs._stable_job_fingerprint(payload)

    stored = _run(metadata={"input_fingerprint": fingerprint})
    jobs._assert_replay_safe(stored, expected_fingerprint=fingerprint)
    result_only = _run(metadata={"result_fingerprint": fingerprint})
    jobs._assert_replay_safe(result_only, expected_fingerprint="other", accepted_fingerprints=(fingerprint,))
    for existing, expected, accepted in (
        (_run(metadata={}), fingerprint, ()),
        (stored, "other", ()),
        (stored, fingerprint, [fingerprint]),
        (stored, 1, ()),
    ):
        with pytest.raises(ValueError):
            jobs._assert_replay_safe(existing, expected_fingerprint=expected, accepted_fingerprints=accepted)


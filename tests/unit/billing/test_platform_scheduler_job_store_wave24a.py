from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

import pytest

from runtime.platform.billing_scheduler_job_store import (
    PlatformSqliteBillingJobRunStore,
    _normalized_run,
    canonical_json_snapshot,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class _Run:
    tenant_id: str
    job_name: str
    run_key: str
    started_at: datetime = NOW
    finished_at: datetime | None = NOW
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not isinstance(self.job_name, str) or not self.job_name.strip():
            raise ValueError("job_name is required")
        if not isinstance(self.run_key, str) or not self.run_key.strip():
            raise ValueError("run_key is required")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be aware")
        if self.finished_at is not None and self.finished_at.tzinfo is None:
            raise ValueError("finished_at must be aware")

    def normalized_copy(self):
        self.validate()
        return replace(
            self,
            tenant_id=self.tenant_id.strip(),
            job_name=self.job_name.strip(),
            run_key=self.run_key.strip(),
            metadata=canonical_json_snapshot(self.metadata),
        )


def _run(**changes) -> _Run:
    values = {
        "tenant_id": " tenant-a ",
        "job_name": " renewal ",
        "run_key": " run-1 ",
        "metadata": {"nested": {"value": 1}, "ids": ("a", "b")},
    }
    values.update(changes)
    return _Run(**values)


def test_json_snapshot_is_finite_normalized_and_deep() -> None:
    assert canonical_json_snapshot(None) is None
    assert canonical_json_snapshot("x") == "x"
    assert canonical_json_snapshot(True) is True
    assert canonical_json_snapshot(1) == 1
    assert canonical_json_snapshot(1.5) == 1.5
    assert canonical_json_snapshot({"ids": (1, 2)}) == {"ids": [1, 2]}
    for value in ({"bad": {1}}, {"bad": float("inf")}, {1: "value"}, {"a": 1, " a ": 2}):
        with pytest.raises(ValueError):
            canonical_json_snapshot(value)


def test_sqlite_store_is_idempotent_deep_and_tuple_list_stable(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite3"
    store = PlatformSqliteBillingJobRunStore(sqlite_path=str(path), run_cls=_Run)
    source = _run()
    saved = store.save(source)
    assert saved == source.normalized_copy()
    assert store.save(source) == saved
    saved.metadata["nested"]["value"] = 99
    fetched = store.get(tenant_id=" tenant-a ", job_name=" renewal ", run_key=" run-1 ")
    assert fetched is not None
    assert fetched.metadata == {"ids": ["a", "b"], "nested": {"value": 1}}
    assert store.get(tenant_id="tenant-a", job_name="renewal", run_key="missing") is None
    with pytest.raises(ValueError, match="collision"):
        store.save(replace(source, metadata={"different": True}))

    reopened = PlatformSqliteBillingJobRunStore(sqlite_path=str(path), run_cls=_Run)
    assert reopened.get(tenant_id="tenant-a", job_name="renewal", run_key="run-1") == fetched


def test_store_rejects_malformed_configuration_queries_and_payloads(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sqlite_path"):
        PlatformSqliteBillingJobRunStore(sqlite_path=" ", run_cls=_Run)
    with pytest.raises(ValueError, match="run_cls"):
        PlatformSqliteBillingJobRunStore(sqlite_path=str(tmp_path / "bad.sqlite3"), run_cls=object())
    with pytest.raises(ValueError, match="validate"):
        _normalized_run(object())

    store = PlatformSqliteBillingJobRunStore(sqlite_path=str(tmp_path / "valid.sqlite3"), run_cls=_Run)
    for kwargs in (
        {"tenant_id": 1, "job_name": "renewal", "run_key": "run-1"},
        {"tenant_id": "tenant-a", "job_name": 1, "run_key": "run-1"},
        {"tenant_id": "tenant-a", "job_name": "renewal", "run_key": 1},
    ):
        with pytest.raises(ValueError):
            store.get(**kwargs)
    for payload in (
        1,
        "[]",
        '{"started_at":1}',
        '{"started_at":"2026-01-01T00:00:00+00:00","finished_at":1}',
    ):
        with pytest.raises((ValueError, TypeError)):
            store._decode(payload)

    unfinished = _run(run_key="unfinished", finished_at=None)
    assert store.save(unfinished).finished_at is None


def test_schema_and_missing_insert_row_fail_explicitly(tmp_path: Path) -> None:
    from contextlib import contextmanager

    schema_path = tmp_path / "schema.sqlite3"
    conn = sqlite3.connect(schema_path)
    conn.execute("CREATE TABLE billing_schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)")
    conn.execute("INSERT INTO billing_schema_version(component, version) VALUES ('job_runs', 2)")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="schema version"):
        PlatformSqliteBillingJobRunStore(sqlite_path=str(schema_path), run_cls=_Run)

    store = PlatformSqliteBillingJobRunStore(sqlite_path=str(tmp_path / "missing.sqlite3"), run_cls=_Run)

    class _Cursor:
        def fetchone(self):
            return None

    class _Connection:
        def execute(self, *args, **kwargs):
            return _Cursor()

    @contextmanager
    def missing_connection():
        yield _Connection()

    store._connect = missing_connection
    with pytest.raises(RuntimeError, match="not persisted"):
        store.save(_run())


def test_normalizer_supports_validate_only_compatibility_objects() -> None:
    class _BareRun:
        def validate(self) -> None:
            return None

    assert isinstance(_normalized_run(_BareRun()), _BareRun)

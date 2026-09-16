from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from application.business_autonomy.contracts import BusinessExecutionResult, ExecutionVerdict
from application.business_autonomy.persistence import PersistentBusinessAutonomyEvidenceStore
from runtime.business_autonomy.bootstrap import _build_distributed_state
from runtime.business_autonomy.distributed_runtime_views import DistributedBusinessAutonomyEvidenceStore
from runtime.business_autonomy.sqlite_distributed_state import (
    SQLiteDistributedEvidenceAppendPort,
    SQLiteStateDatabase,
)
from storage.evidence_store import EvidenceRecord, InMemoryEvidenceStore
from storage.evidence_wiring import canonical_evidence_store_path


def _force_test_sqlite(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("STORAGE_DB_ENGINE", raising=False)
    monkeypatch.setenv("BUSINESAIOS_RUNTIME_REPLICA_COUNT", "1")


def test_business_autonomy_migrates_legacy_evidence_then_writes_only_canonical_store(monkeypatch, tmp_path) -> None:
    _force_test_sqlite(monkeypatch, tmp_path)
    state_path = tmp_path / "runtime" / "business_autonomy_state.sqlite3"
    legacy_database = SQLiteStateDatabase(state_path)
    legacy_port = SQLiteDistributedEvidenceAppendPort(legacy_database)
    created = datetime(2026, 1, 1, tzinfo=UTC)
    legacy = EvidenceRecord.from_legacy(
        tenant_id="tenant-a",
        subject="legacy-business-autonomy",
        evidence_type="execution",
        payload={"legacy": True},
        created_at=created,
        evidence_id="legacy-ba-evidence",
    )
    legacy_port.append(partition_key=legacy.partition_key, payload=legacy.to_row())

    state = _build_distributed_state()
    canonical = state["evidence"]
    migrated = canonical.get(tenant_id="tenant-a", evidence_id=legacy.evidence_id)
    assert migrated is not None
    assert migrated.schema_version == 2
    assert migrated.payload == {"legacy": True}

    business_store = DistributedBusinessAutonomyEvidenceStore(canonical)
    current = business_store.append_result(
        BusinessExecutionResult(
            verdict=ExecutionVerdict.COMPLETED,
            business_id="business-a",
            goal_id="goal-a",
            execution_id="execution-a",
            message="completed",
            adapter_name="test-adapter",
            metadata={"tenant_id": "tenant-a", "decision_id": "decision-a"},
        )
    )
    assert canonical.get(tenant_id="tenant-a", evidence_id=current.evidence_id) == current
    assert canonical_evidence_store_path() == tmp_path / "runtime" / "business_autonomy_evidence.sqlite3"

    with sqlite3.connect(state_path) as connection:
        evidence_rows = connection.execute(
            "SELECT COUNT(*) FROM distributed_evidence WHERE partition_key LIKE 'evidence_%'"
        ).fetchone()[0]
    assert evidence_rows == 1


def test_business_autonomy_compatibility_and_runtime_facades_share_one_projection() -> None:
    canonical = InMemoryEvidenceStore()
    compatibility = PersistentBusinessAutonomyEvidenceStore(backend=canonical)
    runtime = DistributedBusinessAutonomyEvidenceStore(canonical)
    result = BusinessExecutionResult(
        verdict=ExecutionVerdict.COMPLETED,
        business_id="business-a",
        goal_id="goal-a",
        execution_id="execution-shared",
        message="completed",
        adapter_name="test-adapter",
        metadata={
            "tenant_id": "tenant-a",
            "decision_id": "decision-a",
            "action_id": "action-a",
            "semantic_state_id": "state-a",
        },
    )

    first = compatibility.append_result(result)
    second = runtime.append_result(result)

    assert first == second
    assert first.evidence_id == "business-autonomy:execution-shared"
    assert first.action_id == "action-a"
    assert first.lineage["normalization"] == "business-autonomy-result:execution-shared"
    assert first.lineage["derived_fact"] == "state-a"
    assert first.lineage["decision"] == "decision-a"
    assert first.lineage["action"] == "action-a"
    assert first.lineage["outcome"] == "execution-shared"
    assert len(canonical.list_for_tenant(tenant_id="tenant-a")) == 1

    conflict = BusinessExecutionResult(
        verdict=ExecutionVerdict.COMPLETED,
        business_id="business-a",
        goal_id="goal-a",
        execution_id="execution-shared",
        message="tampered",
        adapter_name="test-adapter",
        metadata={
            "tenant_id": "tenant-a",
            "decision_id": "decision-a",
            "action_id": "action-a",
            "semantic_state_id": "state-a",
        },
    )
    with pytest.raises(ValueError, match="replay conflicts with canonical evidence"):
        runtime.append_result(conflict)

import pytest

from application.business_autonomy.contracts import BusinessExecutionResult, ExecutionVerdict
from application.business_autonomy.persistence import (
    PersistentBusinessAutonomyAudit,
    PersistentBusinessAutonomyEvidenceStore,
    PersistentBusinessAutonomyIdempotencyStore,
)
from governance.control_plane_audit_log import PersistentGovernanceAuditLog


@pytest.mark.asyncio
async def test_persistent_business_autonomy_audit_roundtrip(tmp_path) -> None:
    audit = PersistentBusinessAutonomyAudit(PersistentGovernanceAuditLog(tmp_path / "audit.jsonl"))
    audit.record(event_type="business_autonomy.test", business_id="b1", goal_id="g1", detail={"ok": True})
    records = audit.records()
    assert len(records) == 1
    assert records[0].event_type == "business_autonomy.test"


def test_persistent_business_autonomy_idempotency_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store = PersistentBusinessAutonomyIdempotencyStore()
    result = BusinessExecutionResult(
        verdict=ExecutionVerdict.COMPLETED,
        business_id="b1",
        goal_id="g1",
        execution_id="e1",
        message="done",
    )
    store.put("idem-1", result)
    loaded = store.get("idem-1")
    assert loaded is not None
    assert loaded.message == "done"
    assert loaded.verdict is ExecutionVerdict.COMPLETED


def test_persistent_business_autonomy_evidence_store_appends_result(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store = PersistentBusinessAutonomyEvidenceStore()
    result = BusinessExecutionResult(
        verdict=ExecutionVerdict.COMPLETED,
        business_id="b1",
        goal_id="g1",
        execution_id="e1",
        message="done",
        metadata={"tenant_id": "tenant-a"},
    )
    record = store.append_result(result)
    assert record.run_id == "e1"
    items = store.list_recent(tenant_id="tenant-a")
    assert len(items) == 1

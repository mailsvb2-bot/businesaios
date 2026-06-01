from __future__ import annotations

from observability.decision_trace_store import PersistentDecisionTraceStore
from observability.execution_trace_contract import (
    DecisionTraceEvent,
    EffectDisposition,
    ExecutionTraceEvent,
    RuntimeEffectTraceEvent,
    TraceStage,
)
from observability.execution_trace_store import PersistentExecutionTraceStore
from observability.runtime_effect_trace_store import PersistentRuntimeEffectTraceStore
from observability.trace_storage_policy import TraceStoragePolicy


def test_persistent_execution_trace_store_rotates_and_keeps_query_visibility(tmp_path) -> None:
    path = tmp_path / "execution_trace.jsonl"
    store = PersistentExecutionTraceStore(
        path=path,
        storage_policy=TraceStoragePolicy(max_records_per_segment=1, max_bytes_per_segment=10_000, backup_count=2),
    )
    for idx in range(3):
        store.append(
            ExecutionTraceEvent(
                tenant_id="tenant-a",
                trace_id="trace-1",
                run_id="run-1",
                sequence_no=idx,
                stage=TraceStage.EXECUTION,
                event_type=f"event-{idx}",
            )
        )
    store.validate_chain()
    items = store.list_by_trace(tenant_id="tenant-a", trace_id="trace-1")
    assert [item.sequence_no for item in items] == [0, 1, 2]
    assert path.with_suffix(".jsonl.1").exists()


def test_persistent_decision_trace_store_rotates_and_keeps_lookup_visibility(tmp_path) -> None:
    path = tmp_path / "decision_trace.jsonl"
    store = PersistentDecisionTraceStore(
        path=path,
        storage_policy=TraceStoragePolicy(max_records_per_segment=1, max_bytes_per_segment=10_000, backup_count=2),
    )
    for idx in range(3):
        store.append(
            DecisionTraceEvent(
                tenant_id="tenant-a",
                trace_id="trace-1",
                decision_id=f"d-{idx}",
                selected_action="launch_campaign",
                candidate_count=1,
            )
        )
    store.validate_chain()
    assert store.get(tenant_id="tenant-a", decision_id="d-0") is not None
    assert len(store.list_by_trace(tenant_id="tenant-a", trace_id="trace-1")) == 3
    assert path.with_suffix(".jsonl.1").exists()


def test_persistent_runtime_effect_trace_store_rotates_and_keeps_recent_effect_queries(tmp_path) -> None:
    path = tmp_path / "runtime_effect_trace.jsonl"
    store = PersistentRuntimeEffectTraceStore(
        path=path,
        storage_policy=TraceStoragePolicy(max_records_per_segment=1, max_bytes_per_segment=10_000, backup_count=2),
    )
    for idx in range(3):
        store.append(
            RuntimeEffectTraceEvent(
                tenant_id="tenant-a",
                trace_id="trace-1",
                effect_id=f"e-{idx}",
                effect_type="email.send",
                disposition=EffectDisposition.SUCCEEDED,
            )
        )
    store.validate_chain()
    latest = store.list_by_effect_type(tenant_id="tenant-a", effect_type="email.send", limit=2)
    assert [item.effect_id for item in latest] == ["e-2", "e-1"]
    assert path.with_suffix(".jsonl.1").exists()

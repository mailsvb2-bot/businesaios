from __future__ import annotations

from observability.decision_trace_store import InMemoryDecisionTraceStore
from observability.execution_trace_contract import (
    DecisionTraceEvent,
    EffectDisposition,
    ExecutionTraceEvent,
    RuntimeEffectTraceEvent,
    TraceStage,
)
from observability.execution_trace_store import InMemoryExecutionTraceStore
from observability.runtime_effect_trace_store import InMemoryRuntimeEffectTraceStore


TENANT_A = "tenant-a"
TENANT_B = "tenant-b"


def test_execution_trace_store_is_append_only_and_tenant_isolated() -> None:
    store = InMemoryExecutionTraceStore()
    store.append(
        ExecutionTraceEvent(
            tenant_id=TENANT_A,
            trace_id="trace-1",
            run_id="run-1",
            sequence_no=0,
            stage=TraceStage.REQUEST,
            event_type="request.received",
        )
    )
    store.append(
        ExecutionTraceEvent(
            tenant_id=TENANT_B,
            trace_id="trace-2",
            run_id="run-2",
            sequence_no=0,
            stage=TraceStage.REQUEST,
            event_type="request.received",
        )
    )
    store.append(
        ExecutionTraceEvent(
            tenant_id=TENANT_A,
            trace_id="trace-1",
            run_id="run-1",
            sequence_no=1,
            stage=TraceStage.COMPLETED,
            event_type="run.completed",
        )
    )

    store.validate_chain()
    tenant_a = store.list_by_trace(tenant_id=TENANT_A, trace_id="trace-1")
    tenant_b = store.list_by_trace(tenant_id=TENANT_B, trace_id="trace-2")
    assert [item.sequence_no for item in tenant_a] == [0, 1]
    assert len(tenant_b) == 1


def test_decision_trace_store_can_lookup_by_trace_and_decision_id() -> None:
    store = InMemoryDecisionTraceStore()
    event = DecisionTraceEvent(
        tenant_id=TENANT_A,
        trace_id="trace-1",
        decision_id="decision-1",
        selected_action="launch_campaign",
        rationale_summary="best supported action",
        candidate_count=3,
    )
    store.append(event)
    store.validate_chain()
    assert store.get(tenant_id=TENANT_A, decision_id="decision-1") is not None
    items = store.list_by_trace(tenant_id=TENANT_A, trace_id="trace-1")
    assert len(items) == 1
    assert items[0].selected_action == "launch_campaign"


def test_runtime_effect_trace_store_keeps_latest_effects_filterable_by_type() -> None:
    store = InMemoryRuntimeEffectTraceStore()
    for idx in range(3):
        store.append(
            RuntimeEffectTraceEvent(
                tenant_id=TENANT_A,
                trace_id="trace-1",
                effect_id=f"eff-{idx}",
                effect_type="email.send",
                disposition=EffectDisposition.SUCCEEDED,
            )
        )
    store.append(
        RuntimeEffectTraceEvent(
            tenant_id=TENANT_A,
            trace_id="trace-1",
            effect_id="eff-other",
            effect_type="crm.update",
            disposition=EffectDisposition.VERIFIED,
        )
    )
    store.validate_chain()
    latest = store.list_by_effect_type(tenant_id=TENANT_A, effect_type="email.send", limit=2)
    assert [item.effect_id for item in latest] == ["eff-2", "eff-1"]

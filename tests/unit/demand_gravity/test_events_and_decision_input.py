from __future__ import annotations

from datetime import datetime, timezone, UTC

import pytest

from runtime.demand_gravity import (
    DemandChannel,
    DemandGravityDecisionCoreBridge,
    DemandSignal,
    DemandSignalCandidateProducer,
    DemandSignalKind,
    build_decision_input,
    candidate_built_event,
    signal_received_event,
)
from runtime.demand_gravity.events import DemandGravityEvent
from runtime.demand_gravity.no_second_brain import DemandGravitySecondBrainViolation


def _signal() -> DemandSignal:
    return DemandSignal(
        signal_id="sig-1",
        tenant_id="tenant-a",
        business_id="biz-a",
        kind=DemandSignalKind.SEARCH_INTENT,
        channel=DemandChannel.GOOGLE_MAPS,
        observed_at=datetime.now(UTC),
        source_ref="source:1",
        normalized_text="coffee near me",
        confidence=0.8,
        raw_fingerprint="fp-1",
    )


def _candidate():
    return DemandSignalCandidateProducer().build_candidates(
        tenant_id="tenant-a",
        business_id="biz-a",
        signals=(_signal(),),
        correlation_id="corr-1",
    )[0]


def test_signal_and_candidate_events_are_json_safe_and_advisory_only() -> None:
    signal_event = signal_received_event(_signal(), correlation_id="corr-1")
    candidate_event = candidate_built_event(_candidate())

    for event in (signal_event, candidate_event):
        record = event.to_record()
        assert record["event_id"].startswith("dge_")
        assert record["tenant_id"] == "tenant-a"
        assert record["business_id"] == "biz-a"
        assert record["payload"]["decision_owner"] == "DecisionCore"
        assert record["payload"]["execution_allowed"] is False
        assert isinstance(record["occurred_at"], str)


def test_decision_input_is_advisory_only_and_contains_evidence_refs() -> None:
    decision_input = build_decision_input(_candidate())
    payload = decision_input.to_payload()

    assert payload["input_id"].startswith("demand-input:tenant-a:biz-a:dgc_")
    assert payload["goal_type"] == "demand_candidate_review"
    assert payload["decision_owner"] == "DecisionCore"
    assert payload["execution_allowed"] is False
    assert payload["evidence_refs"] == ["source:1"]
    assert payload["idempotency_key"].startswith("demand-gravity:tenant-a:biz-a:dgc_")


class FakeDecisionCore:
    def __init__(self) -> None:
        self.inputs = []

    def ingest_demand_candidate(self, candidate) -> str:
        self.inputs.append(candidate)
        return f"decision:{candidate.candidate_id}"


class MemorySink:
    def __init__(self) -> None:
        self.events: list[DemandGravityEvent] = []

    def append(self, event: DemandGravityEvent) -> str:
        self.events.append(event)
        return event.event_id


def test_bridge_submits_decision_input_and_emits_submission_event_when_sink_is_provided() -> None:
    decision_core = FakeDecisionCore()
    sink = MemorySink()
    candidate = _candidate()

    refs = DemandGravityDecisionCoreBridge(decision_core, event_sink=sink).submit_candidates((candidate,))

    assert refs == (f"decision:{candidate.candidate_id}",)
    assert len(decision_core.inputs) == 1
    assert decision_core.inputs[0].execution_allowed is False
    assert len(sink.events) == 1
    assert sink.events[0].event_type == "DemandCandidateSubmittedToDecisionCore"
    assert sink.events[0].payload["decision_owner"] == "DecisionCore"
    assert sink.events[0].payload["execution_allowed"] is False


def test_event_record_blocks_decision_payloads_recursively() -> None:
    event = DemandGravityEvent(
        event_id="dge_bad",
        event_type="DemandCandidateBuilt",
        tenant_id="tenant-a",
        business_id="biz-a",
        correlation_id="corr-1",
        idempotency_key="idem-1",
        occurred_at=datetime.now(UTC),
        payload={"nested": {"execute_now": True}},
    )

    with pytest.raises(DemandGravitySecondBrainViolation):
        event.to_record()

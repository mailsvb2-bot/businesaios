from __future__ import annotations

from datetime import UTC, datetime

from runtime.demand_gravity import (
    DemandChannel,
    DemandSignal,
    DemandSignalCandidateProducer,
    DemandSignalKind,
    build_decision_input,
    build_demand_gravity_admin_view,
)


def _candidate():
    signal = DemandSignal(
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
    return DemandSignalCandidateProducer().build_candidates(tenant_id="tenant-a", business_id="biz-a", signals=(signal,))[0]


def test_demand_gravity_admin_surface_exposes_evidence_and_decision_input_contracts() -> None:
    view = build_demand_gravity_admin_view(tenant_id="tenant-a", candidates=(_candidate(),), decision_refs=("decision:1",))

    assert view["decision_input_contract"]["input_type"] == "DemandCandidateDecisionInput"
    assert view["decision_input_contract"]["goal_type"] == "demand_candidate_review"
    assert view["decision_input_contract"]["execution_allowed"] is False
    assert view["decision_input_contract"]["decision_owner"] == "DecisionCore"
    assert view["decision_input_contract"]["idempotency_required"] is True
    assert view["decision_input_contract"]["evidence_required"] is True
    assert view["event_contracts"] == [
        "DemandSignalReceived",
        "DemandCandidateBuilt",
        "DemandCandidateSubmittedToDecisionCore",
    ]
    assert view["decision_refs"] == ["decision:1"]


def test_demand_gravity_decision_input_is_not_execution_request() -> None:
    decision_input = build_decision_input(_candidate())
    payload = decision_input.to_payload()

    assert payload["source"] == "demand_gravity"
    assert payload["goal_type"] == "demand_candidate_review"
    assert payload["decision_owner"] == "DecisionCore"
    assert payload["execution_allowed"] is False
    assert "budget_allocation" not in str(payload)
    assert "winner_channel" not in str(payload)

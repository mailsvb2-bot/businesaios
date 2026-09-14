from __future__ import annotations

from application.decision_state.world_model_metadata import (
    attach_world_model_metadata,
    extract_pinned_evidence_refs_from_payload,
    extract_world_model_metadata,
    summarize_pricing_world_state,
)
from contracts.world_model_semantics import WorldModelSemanticRecordV1, WorldModelSemanticViewV1


class FakeState:
    def __init__(self):
        self.meta = {
            "world_model": "canonical_decision_world_model@v1",
            "world_model_kind": "hybrid@v1",
            "pricing_world_model": "pricing-model-42",
            "pricing_world_model_version": "2026-03-07",
            "pricing_world_model_hash": "abc123",
        }
        self.economy = {
            "world_model_source": "canonical",
            "pricing_world_state": {
                "expected_profit": 12.5,
                "expected_revenue": 30.0,
                "conversion_prob_at_price": 0.18,
                "point_elasticity": -1.4,
                "current_price": 49.0,
                "marginal_cost": 11.0,
            },
        }


def test_extract_world_model_metadata():
    state = FakeState()
    meta = extract_world_model_metadata(state=state)

    assert meta["world_model"] == "canonical_decision_world_model@v1"
    assert meta["world_model_kind"] == "hybrid@v1"
    assert meta["pricing_world_model"] == "pricing-model-42"
    assert meta["pricing_world_model_version"] == "2026-03-07"
    assert meta["pricing_world_model_hash"] == "abc123"
    assert meta["world_model_source"] == "canonical"
    assert "pricing_world_state_hash" in meta


def test_attach_world_model_metadata():
    state = FakeState()
    payload = {"decision_id": "d1"}
    out = attach_world_model_metadata(envelope_payload=payload, state=state)

    assert "world_model_meta" in out
    assert out["world_model_meta"]["pricing_world_model"] == "pricing-model-42"


def test_summarize_pricing_world_state():
    state = FakeState()
    summary = summarize_pricing_world_state(state=state)

    assert summary is not None
    assert summary["expected_profit"] == 12.5
    assert summary["point_elasticity"] == -1.4


def test_world_model_evidence_refs_are_pinned_into_signed_payload_metadata():
    state = FakeState()
    record = WorldModelSemanticRecordV1(
        record_id="fact-1", tenant_id="tenant-1", business_id="business-1",
        epistemic_type="fact", key="crm.customer_state", value={"active": True},
        source="crm", occurred_at_ms=10, observed_at_ms=11, recorded_at_ms=12,
        confidence=0.9, authoritative=True, provenance_hash="prov-1",
        evidence_refs=("evidence-1", "evidence-2", "evidence-1"),
    )
    state.world_model_semantics = WorldModelSemanticViewV1(
        state_id="state-1", tenant_id="tenant-1", business_id="business-1",
        generated_at_ms=12, records=(record,),
    )
    payload = attach_world_model_metadata(envelope_payload={"decision_id": "d1"}, state=state)
    assert payload["world_model_meta"]["evidence_refs"] == ["evidence-1", "evidence-2"]
    assert extract_pinned_evidence_refs_from_payload(payload) == ("evidence-1", "evidence-2")

from __future__ import annotations

from application.decision_state.world_model_metadata import (
    attach_world_model_metadata,
    extract_world_model_metadata,
    summarize_pricing_world_state,
)


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

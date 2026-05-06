from __future__ import annotations

from runtime.enforcement.world_model_pin_guard import check_world_model_pin


class FakeState:
    def __init__(self, model_hash: str | None):
        self.meta = {
            "world_model": "canonical_decision_world_model@v1",
            "world_model_kind": "hybrid@v1",
        }
        if model_hash is not None:
            self.meta["pricing_world_model_hash"] = model_hash
            self.meta["pricing_world_model"] = "pricing-prod-1"
            self.meta["pricing_world_model_version"] = "2026-03-07"
        self.economy = {
            "world_model_source": "canonical",
            "pricing_world_state": {
                "expected_profit": 12.0,
            },
        }


def test_world_model_pin_match():
    state = FakeState(model_hash="abc")
    result = check_world_model_pin(
        pinned_meta={
            "pricing_world_model_hash": "abc",
            "pricing_world_model": "pricing-prod-1",
        },
        state=state,
    )
    assert result.ok is True
    assert result.reason == "world_model_pin_match"


def test_world_model_pin_mismatch_non_strict():
    state = FakeState(model_hash="xyz")
    result = check_world_model_pin(
        pinned_meta={
            "pricing_world_model_hash": "abc",
            "pricing_world_model": "pricing-prod-1",
        },
        state=state,
    )
    assert result.reason == "pricing_world_model_hash_mismatch"

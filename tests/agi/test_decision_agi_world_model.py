from __future__ import annotations

from bootstrap.decision_agi_world_model import DecisionAGIWorldModel
from core.world_model.types import WorldModelBuildResult
from kernel.world_state import WorldStateV1


class StubWorldModelService:
    def build_snapshot(self, *, build_input):
        return WorldModelBuildResult(accepted=False, snapshot=None, rejection=None)


class StubStore:
    def get_active_payload(self, *, tenant_id: str, product_id: str):
        return {
            "id": "pricing-prod-1",
            "version": "2026-03-29",
            "kind": "pricing_world_model@v1",
            "demand": {"type": "isoelastic", "a": 120.0, "b": -1.2},
            "conversion": {"type": "logistic", "w0": 0.5, "w1": -0.02, "l2": 1e-6},
            "seasonality": {"type": "dow", "mult": {"0": 1.0}},
        }


def test_decision_agi_world_model_preserves_canonical_enrichment_and_adds_agi_context():
    model = DecisionAGIWorldModel(store=StubStore(), world_model_service=StubWorldModelService())
    state = WorldStateV1(
        schema_version=1,
        tenant_id="tenant-a",
        user={"user_id": "u1", "customer_id": "c1", "sessions": 5, "payments": 100.0, "last_seen": 1_700_000_000.0},
        session={"channel": "web", "geo": "nl", "inbound_leads": 0, "outbound_count": 0},
        product={"product_id": "p1", "business_id": "b1", "price": 49.0, "currency": "EUR"},
        economy={},
        timestamp_ms=1710000000000,
        meta={
            "business_id": "b1",
            "business_memory_evidence": {"active_goals": ["increase revenue safely"]},
            "runtime_capabilities": {"analytics_read": {"status": "ok"}},
        },
        user_id="u1",
    )
    enriched = model.enrich_state(state)
    assert enriched is not state
    assert "predicted_ltv" in enriched.economy
    assert "pricing_world_state" in enriched.economy
    assert enriched.meta["world_model"] == "decision_agi_world_model@v1"
    assert enriched.meta["world_model_kind"] == "decision_agi@v1"
    assert enriched.meta["decision_agi_base_world_model_kind"] == "hybrid@v1"
    assert isinstance(enriched.meta.get("decision_agi"), dict)
    assert isinstance(enriched.meta.get("decision_agi_summary"), dict)
    assert enriched.meta["decision_agi_summary"]["selected_goal"] == "increase revenue safely"
    assert enriched.meta["decision_agi_summary"]["no_second_brain"] is True


def test_decision_agi_world_model_is_noop_safe_when_snapshot_inputs_are_incomplete():
    model = DecisionAGIWorldModel(store=StubStore(), world_model_service=StubWorldModelService())
    state = WorldStateV1(
        schema_version=1,
        tenant_id="tenant-a",
        user={"user_id": "u1"},
        session={},
        product={},
        economy={},
        timestamp_ms=1710000000000,
        meta={},
        user_id="u1",
    )
    enriched = model.enrich_state(state)
    assert enriched.meta["world_model"] == "decision_agi_world_model@v1"
    assert enriched.meta["decision_agi_world_snapshot_status"] == "unavailable"
    assert isinstance(enriched.meta["decision_agi"], dict)


class FailingReasoningEngine:
    def build_summary(self, *, state, world_snapshot=None):
        raise RuntimeError("reasoning blew up")


def test_decision_agi_world_model_reasoning_failure_is_fail_closed():
    model = DecisionAGIWorldModel(
        store=StubStore(),
        world_model_service=StubWorldModelService(),
        reasoning_engine=FailingReasoningEngine(),
    )

    state = WorldStateV1(
        schema_version=1,
        tenant_id="tenant-a",
        user={"user_id": "u1", "customer_id": "c1"},
        session={"channel": "web", "geo": "nl"},
        product={"product_id": "p1", "business_id": "b1", "price": 49.0, "currency": "EUR"},
        economy={},
        timestamp_ms=1710000000000,
        meta={"business_id": "b1"},
        user_id="u1",
    )

    enriched = model.enrich_state(state)

    assert enriched.meta["decision_agi_reasoning_status"] == "failed_closed"
    assert enriched.meta["decision_agi_summary"]["reasoning_status"] == "failed_closed"
    assert enriched.meta["decision_agi"]["explainability"]["reasoning_failed_closed"] is True

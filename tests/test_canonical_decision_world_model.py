from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel
from contracts.world_model_semantics import WorldModelSemanticViewV1


@dataclass(frozen=True)
class FakeWorldState:
    schema_version: int
    user: dict[str, Any]
    session: dict[str, Any]
    product: dict[str, Any]
    economy: dict[str, Any]
    timestamp_ms: int
    tenant_id: str = "tenant-1"
    meta: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None
    safe_mode: bool = False
    capital: float = 0.0
    horizon_state: str = "stable"
    behavior: dict[str, Any] | None = None
    price_constraints: dict[str, Any] | None = None
    deployment_proposal: dict[str, Any] | None = None
    manual_override: bool = False
    world_model_semantics: WorldModelSemanticViewV1 | None = None


class FakeStore:
    def get_active_payload(self, *, tenant_id: str, product_id: str):
        assert tenant_id == "tenant-1"
        assert product_id == "prod-1"
        return {
            "kind": "pricing_world_model@v1",
            "demand": {"type": "isoelastic", "a": 120.0, "b": -1.2},
            "conversion": {"type": "logistic", "w0": 0.5, "w1": -0.02, "l2": 1e-6},
            "seasonality": {"type": "dow", "mult": {"0": 1.0}},
        }


def test_canonical_decision_world_model_enriches_ltv_and_pricing():
    model = CanonicalDecisionWorldModel(store=FakeStore(), kind="hybrid@v1")
    state = FakeWorldState(
        schema_version=1,
        user={"user_id": "u1", "sessions": 5, "payments": 100.0, "last_seen": 1_700_000_000.0},
        session={"channel": "web", "geo": "NL", "device": "desktop"},
        product={"product_id": "prod-1", "price": 49.0, "currency": "EUR"},
        economy={},
        timestamp_ms=1_700_000_100_000,
        tenant_id="tenant-1",
        user_id="u1",
    )

    enriched = model.enrich_state(state)

    assert isinstance(enriched.economy, dict)
    assert "predicted_ltv" in enriched.economy
    assert "pricing_world_state" in enriched.economy

    ws = enriched.economy["pricing_world_state"]
    assert isinstance(ws, dict)
    assert "expected_profit" in ws
    assert "expected_revenue" in ws

    assert enriched.meta["world_model"] == "canonical_decision_world_model@v1"
    assert enriched.meta["world_model_kind"] == "hybrid@v1"


class FakeStateSnapshotStore:
    def __init__(self, semantic_view: WorldModelSemanticViewV1) -> None:
        self.semantic_view = semantic_view

    def load_latest(self, *, tenant_id: str, business_id: str):
        assert tenant_id == "tenant-1"
        assert business_id == "business-1"
        return type(
            "Snapshot",
            (),
            {
                "tenant_id": tenant_id,
                "business_id": business_id,
                "state_id": "state-1",
                "semantic_view": self.semantic_view,
            },
        )()


def test_canonical_decision_world_model_attaches_canonical_business_semantics():
    semantic_view = WorldModelSemanticViewV1(
        state_id="state-1",
        tenant_id="tenant-1",
        business_id="business-1",
        generated_at_ms=1_700_000_000_000,
    )
    model = CanonicalDecisionWorldModel(
        store=FakeStore(),
        kind="hybrid@v1",
        state_snapshot_store=FakeStateSnapshotStore(semantic_view),
    )
    state = FakeWorldState(
        schema_version=1,
        user={"user_id": "u1"},
        session={},
        product={"product_id": "prod-1", "business_id": "business-1", "price": 49.0},
        economy={},
        timestamp_ms=1_700_000_100_000,
        tenant_id="tenant-1",
        user_id="u1",
    )

    enriched = model.enrich_state(state)

    assert enriched.world_model_semantics is semantic_view
    assert enriched.meta["canonical_business_state_id"] == "state-1"

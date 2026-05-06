from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from application.decision_state.world_model_replay import replay_state_against_world_model
from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel


@dataclass(frozen=True)
class FakeWorldState:
    schema_version: int
    user: Dict[str, Any]
    session: Dict[str, Any]
    product: Dict[str, Any]
    economy: Dict[str, Any]
    timestamp_ms: int
    tenant_id: str = "tenant-1"
    meta: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    safe_mode: bool = False
    capital: float = 0.0
    horizon_state: str = "stable"
    behavior: Optional[Dict[str, Any]] = None
    price_constraints: Optional[Dict[str, Any]] = None
    deployment_proposal: Optional[Dict[str, Any]] = None
    manual_override: bool = False


class FakeStore:
    def get_active_payload(self, *, tenant_id: str, product_id: str):
        return {
            "id": "pricing-prod-1",
            "version": "2026-03-07",
            "kind": "pricing_world_model@v1",
            "demand": {"type": "isoelastic", "a": 120.0, "b": -1.2},
            "conversion": {"type": "logistic", "w0": 0.5, "w1": -0.02, "l2": 1e-6},
            "seasonality": {"type": "dow", "mult": {"0": 1.0}},
        }


def test_replay_state_against_world_model():
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

    replay = replay_state_against_world_model(
        state=state,
        world_model=model,
    )

    assert "world_model_meta" in replay
    assert replay["world_model_meta"]["pricing_world_model"] == "pricing-prod-1"
    assert "constraint_explainability" in replay

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel


@dataclass(frozen=True)
class FakeWorldState:
    schema_version: int
    user: dict[str, Any]
    session: dict[str, Any]
    product: dict[str, Any]
    economy: dict[str, Any]
    timestamp_ms: int
    tenant_id: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None


class GuardStore:
    def get_active_payload(self, *, tenant_id: str, product_id: str):
        raise AssertionError("pricing store must not be queried without canonical tenant")


def test_canonical_world_model_skips_pricing_when_tenant_is_missing_or_noncanonical() -> None:
    model = CanonicalDecisionWorldModel(store=GuardStore(), kind="hybrid@v1")
    state = FakeWorldState(
        schema_version=1,
        user={"user_id": "u1", "sessions": 3, "payments": 10.0},
        session={"channel": "web"},
        product={"product_id": "prod-1", "price": 49.0, "currency": "EUR"},
        economy={},
        timestamp_ms=1_700_000_100_000,
        tenant_id="default",
        user_id="u1",
    )

    enriched = model.enrich_state(state)

    assert "predicted_ltv" in enriched.economy
    assert "pricing_world_state" not in enriched.economy
    assert enriched.meta["pricing_world_model_skipped"] is True
    assert enriched.meta["pricing_world_model_skip_reason"] == "missing_or_noncanonical_tenant"

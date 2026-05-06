from __future__ import annotations

from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel
from ports.world_model import DecisionWorldModelPort


class DummyStore:
    def get_active_payload(self, *, tenant_id: str, product_id: str):
        return None


def test_canonical_world_model_implements_port():
    wm = CanonicalDecisionWorldModel(store=DummyStore(), kind="hybrid@v1")
    assert isinstance(wm, DecisionWorldModelPort)

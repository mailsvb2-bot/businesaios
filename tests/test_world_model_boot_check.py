from __future__ import annotations

from bootstrap.world_model_boot_check import verify_boot_world_model_integrity
from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel


class DummyStore:
    def get_active_payload(self, *, tenant_id: str, product_id: str):
        return None


def test_verify_boot_world_model_integrity_ok():
    wm = CanonicalDecisionWorldModel(store=DummyStore(), kind="hybrid@v1")
    result = verify_boot_world_model_integrity(world_model=wm)

    assert result["ok"] is True
    assert result["implementation"].endswith(".CanonicalDecisionWorldModel")

from __future__ import annotations

from bootstrap.decision_agi_world_model import DecisionAGIWorldModel
from core.ai.decision_core import DecisionCore
from ports.world_model import DecisionWorldModelPort


class DummySelector:
    pass


class DummyKeyring:
    pass


class DummySchemas:
    pass


class DummyStore:
    pass


class DummyEventLog:
    pass


class StubStore:
    def get_active_payload(self, *, tenant_id: str, product_id: str):
        return None


class StubWorldModelService:
    def build_snapshot(self, *, build_input):
        raise RuntimeError("boom")


def test_decision_core_accepts_agi_world_model_as_canonical_port() -> None:
    world_model = DecisionAGIWorldModel(store=StubStore(), world_model_service=StubWorldModelService())
    assert isinstance(world_model, DecisionWorldModelPort)
    core = DecisionCore(
        selector=DummySelector(),
        keyring=DummyKeyring(),
        schema_registry=DummySchemas(),
        snapshot_store=DummyStore(),
        event_log=DummyEventLog(),
        world_model=world_model,
    )
    assert core is not None

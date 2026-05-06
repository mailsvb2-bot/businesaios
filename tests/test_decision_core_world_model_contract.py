from __future__ import annotations

import pytest

from core.ai.decision_core import DecisionCore


class DummySelector: ...
class DummyKeyring: ...
class DummySchemas: ...
class DummyStore: ...
class DummyEventLog: ...
class BadWorldModel: ...


def test_decision_core_rejects_non_port_world_model() -> None:
    with pytest.raises(TypeError):
        DecisionCore(
            selector=DummySelector(),
            keyring=DummyKeyring(),
            schema_registry=DummySchemas(),
            snapshot_store=DummyStore(),
            event_log=DummyEventLog(),
            world_model=BadWorldModel(),
        )

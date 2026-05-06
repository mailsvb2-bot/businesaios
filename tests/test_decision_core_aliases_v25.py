import time

from core.ai.world_state import WorldStateV1
from core.ai.policy_registry import PolicyRegistry
from core.policies.selector import PolicySelector
from core.ai.schema_registry import SchemaRegistry, DecisionSchema
from core.ai.snapshot_store import MemorySnapshotStore
from core.ai.decision_core import DecisionCore
from core.security.keyring import Keyring
from core.events.log import EventLog
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _Policy:
    id = "p@v1"

    def propose(self, state):
        return type("O", (), {"action": "send_message@v1", "payload": {"user_id": "u1", "text": "hi"}})()


def _build_core():
    schemas = SchemaRegistry()
    schemas.register(
        "send_message@v1",
        1,
        DecisionSchema(required={"user_id", "text"}, optional=set(), field_types={"user_id": str, "text": str}),
    )
    registry = PolicyRegistry()
    registry.register(_Policy())
    selector = PolicySelector(registry)
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    events = EventLog(MemoryEventStore(), tenant="default")
    return DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events)


def _state():
    return WorldStateV1(1, {}, {}, {}, {}, int(time.time() * 1000), tenant_id="default", user_id="u1")


def test_optimize_and_issue_aliases_route_to_single_decider():
    core = _build_core()
    env_a = core.optimize(_state())
    env_b = core.issue(_state())
    assert env_a.decision.action == "send_message@v1"
    assert env_b.decision.action == "send_message@v1"
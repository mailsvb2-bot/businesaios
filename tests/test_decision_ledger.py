import time

import pytest

from core.ai.decision_core import DecisionCore
from core.ai.policy_registry import PolicyRegistry
from core.ai.schema_registry import DecisionSchema, SchemaRegistry
from core.ai.snapshot_store import MemorySnapshotStore
from core.ai.world_state import WorldStateV1
from core.events.log import EventLog
from core.policies.selector import PolicySelector
from core.security.keyring import Keyring
from runtime.executor import RuntimeExecutor
from runtime.guard import RuntimeGuard
from runtime.handlers import ActionHandlerRegistry
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.platform.ledger.sqlite_ledger import SqliteLedger


class PolicyA:
    id = "p@v1"

    def propose(self, state):
        return type("O", (), {"action": "noop@v1", "payload": {}})()


def test_exactly_once_via_guard_and_ledger(tmp_path):
    schemas = SchemaRegistry()
    schemas.register("noop@v1", 1, DecisionSchema(required=set(), optional=set(), field_types={}))

    preg = PolicyRegistry()
    preg.register(PolicyA())
    selector = PolicySelector(preg)

    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    events = EventLog(MemoryEventStore(), tenant="default")
    core = DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events)

    ledger_ctx = SqliteLedger(str(tmp_path / "ledger.db"))
    ledger = ledger_ctx.__enter__()
    guard = RuntimeGuard(keyring, ledger, schemas, event_log=events)

    handlers = ActionHandlerRegistry()
    handlers.register("noop@v1", lambda payload, effects, env: None)

    executor = RuntimeExecutor(guard, handlers, events, policy_registry=preg, decision_core=core)

    state = WorldStateV1(1, {}, {}, {}, {}, int(time.time() * 1000), user_id="u1")
    env = core.optimize(state)

    result = executor.execute(env)
    assert result.ok is True
    with pytest.raises(RuntimeError, match="^DUPLICATE_EXECUTION$"):
        executor.execute(env)

    ledger_ctx.__exit__(None, None, None)

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
        return type("O", (), {"action": "send_message@v1", "payload": {"user_id": state.user_id, "text": "hi"}})()


def test_effects_are_callable_only_during_executor_window(tmp_path):
    schemas = SchemaRegistry()
    schemas.register("send_message@v1", 1, DecisionSchema(required={"user_id", "text"}, optional=set(), field_types={"user_id": str, "text": str}))

    preg = PolicyRegistry(); preg.register(PolicyA())
    selector = PolicySelector(preg)

    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    events = EventLog(MemoryEventStore(), tenant="default")
    core = DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events)

    ledger_ctx = SqliteLedger(str(tmp_path / "ledger.db"))
    ledger = ledger_ctx.__enter__()
    guard = RuntimeGuard(keyring, ledger, schemas, event_log=events)

    handlers = ActionHandlerRegistry()
    handlers.register(
        "send_message@v1",
        lambda payload, effects, env: effects.send_message(
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            user_id=payload["user_id"],
            text=payload["text"],
        ),
    )
    executor = RuntimeExecutor(guard, handlers, events, policy_registry=preg, decision_core=core)

    # Direct call (no capability window) must fail
    with pytest.raises(RuntimeError):
        executor._effects.send_message(decision_id="d", correlation_id="c", user_id="u1", text="hack")

    state = WorldStateV1(1, {}, {}, {}, {}, int(time.time() * 1000), user_id="u1")
    env = core.optimize(state)
    executor.execute(env)

    ledger_ctx.__exit__(None, None, None)

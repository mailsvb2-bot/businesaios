from core.tenancy.tenant import current_tenant_id
import time
import random
import pytest

from core.ai.world_state import WorldStateV1
from core.ai.policy_registry import PolicyRegistry
from core.policies.selector import PolicySelector
from core.ai.schema_registry import SchemaRegistry, DecisionSchema
from core.ai.snapshot_store import MemorySnapshotStore
from core.ai.decision_core import DecisionCore
from core.security.keyring import Keyring
from core.events.log import EventLog

from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.platform.ledger.sqlite_ledger import SqliteLedger

from runtime.guard import RuntimeGuard
from runtime.handlers import ActionHandlerRegistry
from runtime.executor import RuntimeExecutor


class _Policy:
    id = "p@v1"

    def __init__(self, action: str = "send_message@v1"):
        self._action = action

    def propose(self, state):
        # payload is deterministic for a fixed state
        return type("O", (), {"action": self._action, "payload": {"user_id": state.user_id, "text": "hi"}})()


def _build(tmp_path, *, revoked=False, ttl_ms=60_000, action="send_message@v1"):
    schemas = SchemaRegistry()
    schemas.register(
        "send_message@v1",
        1,
        DecisionSchema(required={"user_id", "text"}, optional=set(), field_types={"user_id": str, "text": str}),
    )

    preg = PolicyRegistry()
    preg.register(_Policy(action=action))
    selector = PolicySelector(preg)

    keyring = Keyring({"k1": {"secret": b"s1", "revoked": revoked}}, "k1")
    events = EventLog(MemoryEventStore(), tenant="default")
    core = DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events, ttl_ms=ttl_ms)

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

    state = WorldStateV1(
        schema_version=1,
        user={},
        session={},
        product={},
        economy={},
        timestamp_ms=int(time.time() * 1000),
        tenant_id=current_tenant_id(),
        user_id="u1",
    )
    return core, executor, state, ledger_ctx


def test_payload_tamper_fails(tmp_path):
    core, executor, state, ledger_ctx = _build(tmp_path)
    env = core.optimize(state)
    # tamper payload -> hash mismatch
    env.decision.payload["text"] = "bye"
    with pytest.raises(Exception):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_signature_tamper_fails(tmp_path):
    core, executor, state, ledger_ctx = _build(tmp_path)
    env = core.optimize(state)
    from dataclasses import replace
    env = replace(env, signature=("00" * 32))
    with pytest.raises(Exception):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_unknown_action_rejected(tmp_path):
    core, executor, state, ledger_ctx = _build(tmp_path, action="unknown_action@v1")
    with pytest.raises(Exception):
        env = core.optimize(state)
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_duplicate_execution_rejected(tmp_path):
    core, executor, state, ledger_ctx = _build(tmp_path)
    env = core.optimize(state)
    executor.execute(env)
    with pytest.raises(Exception):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_ttl_expiry_rejected(tmp_path):
    core, executor, state, ledger_ctx = _build(tmp_path, ttl_ms=5)
    env = core.optimize(state)
    time.sleep(0.02)
    with pytest.raises(Exception):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_replay_after_key_revoke_rejected(tmp_path):
    core, executor, state, ledger_ctx = _build(tmp_path)
    env = core.optimize(state)
    # revoke active key after issuing
    executor._guard._keyring._keys["k1"].revoked = True  # type: ignore[attr-defined]
    with pytest.raises(Exception):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_fuzz_payload_mutations_fail(tmp_path):
    core, executor, state, ledger_ctx = _build(tmp_path)
    env = core.optimize(state)

    rnd = random.Random(1337)
    for _ in range(25):
        mutated = core.optimize(state)
        # random mutation: change or add key
        if rnd.random() < 0.5:
            mutated.decision.payload["text"] = "x" * rnd.randint(1, 20)
        else:
            mutated.decision.payload["extra"] = "boom"
        with pytest.raises(Exception):
            executor.execute(mutated)
    ledger_ctx.__exit__(None, None, None)
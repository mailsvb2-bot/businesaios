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
from core.tenancy.tenant import current_tenant_id
from runtime.executor import RuntimeExecutor
from runtime.guard import RuntimeGuard
from runtime.handlers import ActionHandlerRegistry
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.platform.ledger.sqlite_ledger import SqliteLedger


class PolicyA:
    id = "p@v1"

    def propose(self, state):
        return type("O", (), {"action": "send_message@v1", "payload": {"user_id": "u1", "text": "hi"}})()


def build(tmp_path, *, revoked=False, ttl_ms=60_000):
    schemas = SchemaRegistry()
    schemas.register(
        "send_message@v1",
        1,
        DecisionSchema(required={"user_id", "text"}, optional=set(), field_types={"user_id": str, "text": str}),
    )

    preg = PolicyRegistry()
    preg.register(PolicyA())
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
    core, executor, state, ledger_ctx = build(tmp_path)
    env = core.optimize(state)
    tampered = env.decision.payload.copy()
    tampered["text"] = "evil"
    env = type(env)(decision=env.decision.__class__(**{**env.decision.__dict__, "payload": tampered}), payload_hash=env.payload_hash, signature=env.signature, kid=env.kid, envelope_version=env.envelope_version)
    with pytest.raises(RuntimeError):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_signature_tamper_fails(tmp_path):
    core, executor, state, ledger_ctx = build(tmp_path)
    env = core.optimize(state)
    bad = type(env)(decision=env.decision, payload_hash=env.payload_hash, signature="AAAA", kid=env.kid, envelope_version=env.envelope_version)
    with pytest.raises(RuntimeError):
        executor.execute(bad)
    ledger_ctx.__exit__(None, None, None)


def test_unknown_kid_fails(tmp_path):
    core, executor, state, ledger_ctx = build(tmp_path)
    env = core.optimize(state)
    bad = type(env)(decision=env.decision, payload_hash=env.payload_hash, signature=env.signature, kid="k999", envelope_version=env.envelope_version)
    with pytest.raises(RuntimeError):
        executor.execute(bad)
    ledger_ctx.__exit__(None, None, None)


def test_unknown_action_fails(tmp_path):
    schemas = SchemaRegistry()
    schemas.register("send_message@v1", 1, DecisionSchema(required={"user_id", "text"}, optional=set(), field_types={"user_id": str, "text": str}))
    preg = PolicyRegistry()

    class BadPolicy:
        id = "bad@v1"
        def propose(self, state):
            return type("O", (), {"action": "unknown@v1", "payload": {}})()

    preg.register(BadPolicy())
    selector = PolicySelector(preg)
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    events = EventLog(MemoryEventStore(), tenant="default")
    core = DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events)
    state = WorldStateV1(1, {}, {}, {}, {}, int(time.time()*1000), user_id="u1")
    with pytest.raises(ValueError):
        core.optimize(state)


def test_duplicate_execution_fails(tmp_path):
    core, executor, state, ledger_ctx = build(tmp_path)
    env = core.optimize(state)
    executor.execute(env)
    with pytest.raises(RuntimeError):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_ttl_expiry_fails(tmp_path):
    core, executor, state, ledger_ctx = build(tmp_path, ttl_ms=1)
    env = core.optimize(state)
    time.sleep(0.01)
    with pytest.raises(RuntimeError):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_telegram_mode_requires_numeric_chat_id(tmp_path, monkeypatch):
    # In RUN_MODE=telegram, payload.user_id is used as Telegram chat_id.
    # The runtime law must prevent accidental sends to non-numeric ids (e.g., demo_user).
    monkeypatch.setenv("RUN_MODE", "telegram")

    core, executor, state, ledger_ctx = build(tmp_path)
    env = core.optimize(state)
    with pytest.raises(RuntimeError):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)


def test_replay_after_revoke_fails(tmp_path):
    core, executor, state, ledger_ctx = build(tmp_path)
    env = core.optimize(state)
    # revoke key after issuance
    executor._guard._keyring.revoke(env.kid)
    with pytest.raises(RuntimeError):
        executor.execute(env)
    ledger_ctx.__exit__(None, None, None)

from core.tenancy.tenant import current_tenant_id
import time

from core.ai.world_state import WorldStateV1
from core.ai.policy_registry import PolicyRegistry
from core.policies.selector import PolicySelector
from core.ai.schema_registry import SchemaRegistry, DecisionSchema
from core.ai.snapshot_store import MemorySnapshotStore
from core.ai.decision_core import DecisionCore
from core.ai.decision_archive import MemoryDecisionArchive
from core.security.keyring import Keyring
from core.events.log import EventLog

from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.platform.ledger.sqlite_ledger import SqliteLedger

from runtime.guard import RuntimeGuard
from runtime.handlers import ActionHandlerRegistry
from runtime.executor import RuntimeExecutor
from runtime.replay import ReplayEngine


class PolicyA:
    id = "p@v1"

    def propose(self, state):
        return type("O", (), {"action": "send_message@v1", "payload": {"user_id": "u1", "text": "hi"}})()


def _build_executor(tmp_path, *, keyring, schemas, preg, events, core):
    ledger_ctx = SqliteLedger(str(tmp_path))
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
    return executor, ledger_ctx


def test_ring_invariant_deterministic_execution(tmp_path):
    schemas = SchemaRegistry()
    schemas.register(
        "send_message@v1",
        1,
        DecisionSchema(required={"user_id", "text"}, optional=set(), field_types={"user_id": str, "text": str}),
    )

    preg = PolicyRegistry()
    preg.register(PolicyA())
    selector = PolicySelector(preg)

    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    events = EventLog(MemoryEventStore(), tenant="default")

    archive = MemoryDecisionArchive()
    core = DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events, decision_archive=archive)

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

    env = core.optimize(state)

    # Execute original
    ex1, ledger1 = _build_executor(tmp_path / "l1.db", keyring=keyring, schemas=schemas, preg=preg, events=events, core=core)
    r1 = ex1.execute(env)

    # Replay envelope and execute on a fresh ledger (exactly-once is per-ledger)
    engine = ReplayEngine(archive)
    env2 = engine.replay(env.decision.decision_id)
    ex2, ledger2 = _build_executor(tmp_path / "l2.db", keyring=keyring, schemas=schemas, preg=preg, events=events, core=core)
    r2 = ex2.execute(env2)

    assert r1.ok and r2.ok
    assert r1.output == r2.output

    ledger1.__exit__(None, None, None)
    ledger2.__exit__(None, None, None)
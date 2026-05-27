import time

from core.ai.decision_core import DecisionCore
from core.ai.policy_registry import PolicyRegistry
from core.ai.schema_registry import DecisionSchema, SchemaRegistry
from core.ai.snapshot_store import MemorySnapshotStore
from core.ai.world_state import WorldStateV1
from core.events.log import EventLog
from core.policies.selector import PolicySelector
from core.reward.reward_engine import RewardEngine
from core.security.keyring import Keyring
from core.tenancy.tenant import current_tenant_id
from runtime.executor import RuntimeExecutor
from runtime.guard import RuntimeGuard
from runtime.handlers import ActionHandlerRegistry
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.platform.ledger.sqlite_ledger import SqliteLedger


class PayPolicy:
    id = "pay@v1"

    def propose(self, state):
        return type(
            "O",
            (),
            {"action": "capture_payment@v1", "payload": {"user_id": state.user_id, "amount": 1000, "currency": "RUB"}},
        )()


def test_required_proof_events_emitted(tmp_path):
    import core.ai.decision_core as dc

    def _allow_gate(**kwargs):
        return True, "ok", {}

    dc.gate_action_or_raise = _allow_gate

    schemas = SchemaRegistry()
    schemas.register(
        "capture_payment@v1",
        1,
        DecisionSchema(
            required={"user_id", "amount", "currency"},
            optional=set(),
            field_types={"user_id": str, "amount": int, "currency": str},
        ),
    )

    preg = PolicyRegistry()
    preg.register(PayPolicy())
    selector = PolicySelector(preg)

    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    store = MemoryEventStore()
    events = EventLog(store, tenant="default")

    core = DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events)

    ledger_ctx = SqliteLedger(str(tmp_path / "ledger.db"))
    ledger = ledger_ctx.__enter__()
    guard = RuntimeGuard(keyring, ledger, schemas, event_log=events)

    handlers = ActionHandlerRegistry()
    handlers.register(
        "capture_payment@v1",
        lambda payload, effects, env: {"ok": True},
    )

    reward = RewardEngine()
    executor = RuntimeExecutor(guard, handlers, events, policy_registry=preg, reward_engine=reward, decision_core=core)

    state = WorldStateV1(
        schema_version=1,
        user={},
        session={},
        product={},
        economy={},
        timestamp_ms=int(time.time() * 1000),
        tenant_id=current_tenant_id(),
        user_id="u123",
    )

    env = core.optimize(state)
    executor.execute(env)

    types = [e["event_type"] for e in store]
    assert "decision_issued" in types
    assert "ai_decision_trace" in types
    assert "ledger_executed" in types
    assert "decision_executed" in types

    ledger_ctx.__exit__(None, None, None)

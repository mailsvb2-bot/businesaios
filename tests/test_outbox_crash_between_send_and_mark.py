import time

import pytest

from core.ai.world_state import WorldStateV1
from core.ai.policy_registry import PolicyRegistry
from core.policies.selector import PolicySelector
from core.ai.schema_registry import SchemaRegistry, DecisionSchema
from core.ai.snapshot_store import MemorySnapshotStore
from core.ai.decision_core import DecisionCore
from core.security.keyring import Keyring
from core.events.log import EventLog

from runtime.platform.event_store.sqlite_event_store import SqliteEventStore
from runtime.platform.ledger.sqlite_ledger import SqliteLedger
from observability.platform.decision_archive.sqlite_decision_archive import SqliteDecisionArchive
from runtime.platform.outbox.sqlite_outbox import SqliteOutbox

from runtime.guard import RuntimeGuard
from runtime.handlers import ActionHandlerRegistry
from runtime.executor import RuntimeExecutor


class PolicyA:
    id = "p@v1"

    def propose(self, state):
        return type("O", (), {"action": "send_message@v1", "payload": {"user_id": "u1", "text": "hi"}})()


def test_crash_between_effect_and_mark_delivered_does_not_duplicate(tmp_path):
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

    # Durable stores
    event_store_ctx = SqliteEventStore(str(tmp_path / "events.db"))
    store = event_store_ctx.__enter__()
    events = EventLog(store, tenant="default")

    archive_ctx = SqliteDecisionArchive(str(tmp_path / "archive.db"))
    archive = archive_ctx.__enter__()

    outbox_ctx = SqliteOutbox(str(tmp_path / "outbox.db"))
    outbox = outbox_ctx.__enter__()

    core = DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events, decision_archive=archive)

    ledger_ctx = SqliteLedger(str(tmp_path / "ledger.db"))
    ledger = ledger_ctx.__enter__()
    guard = RuntimeGuard(keyring, ledger, schemas, event_log=events)

    calls = []
    handlers = ActionHandlerRegistry()

    def handler(payload, _effects, env):
        calls.append(env.decision.decision_id)
        # Simulate effects proof event written (like real effects would do).
        events.emit(
            event_type="message_sent",
            source="tests",
            user_id=payload["user_id"],
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            payload={"ok": True},
        )
        return True

    handlers.register("send_message@v1", handler)

    # Monkeypatch outbox.mark_delivered to simulate a crash right after effects.
    real_mark = outbox.mark_delivered

    def boom(decision_id: str):
        raise RuntimeError("CRASH_SIM")

    outbox.mark_delivered = boom  # type: ignore

    executor = RuntimeExecutor(guard, handlers, events, policy_registry=preg, decision_core=core, outbox=outbox, decision_archive=archive)

    state = WorldStateV1(1, {}, {}, {}, {}, int(time.time() * 1000), user_id="u1")
    env = core.optimize(state)

    with pytest.raises(RuntimeError):
        executor.execute(env)

    # Restore mark_delivered and run recovery.
    outbox.mark_delivered = real_mark  # type: ignore

    # Recovery should NOT re-run handler because proof exists and status is delivering.
    executor.execute_recovery(env)

    assert calls.count(env.decision.decision_id) == 1

    ledger_ctx.__exit__(None, None, None)
    archive_ctx.__exit__(None, None, None)
    outbox_ctx.__exit__(None, None, None)
    event_store_ctx.__exit__(None, None, None)
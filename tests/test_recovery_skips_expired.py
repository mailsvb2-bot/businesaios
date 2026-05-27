import time

from core.ai.decision_core import DecisionCore
from core.ai.policy_registry import PolicyRegistry
from core.ai.schema_registry import DecisionSchema, SchemaRegistry
from core.ai.snapshot_store import MemorySnapshotStore
from core.ai.world_state import WorldStateV1
from core.events.log import EventLog
from core.policies.selector import PolicySelector
from core.security.keyring import Keyring
from observability.platform.decision_archive.sqlite_decision_archive import SqliteDecisionArchive
from runtime.executor import RuntimeExecutor
from runtime.guard import MAX_REPLAY_MS, RuntimeGuard
from runtime.handlers import ActionHandlerRegistry
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.platform.ledger.sqlite_ledger import SqliteLedger
from runtime.platform.outbox.sqlite_outbox import SqliteOutbox
from runtime.recovery import recover_pending


class _Clock:
    def __init__(self, now_ms: int):
        self._now_ms = int(now_ms)

    def now_ms(self) -> int:
        return int(self._now_ms)


class PolicyA:
    id = "p@v1"

    def propose(self, state):
        return type("O", (), {"action": "send_message@v1", "payload": {"user_id": "u1", "text": "hi"}})()


def test_recovery_quarantines_expired_envelopes_instead_of_crashing(tmp_path):
    """Boot recovery must never brick runtime on stale envelopes."""

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

    archive_ctx = SqliteDecisionArchive(str(tmp_path / "archive.db"))
    archive = archive_ctx.__enter__()
    outbox_ctx = SqliteOutbox(str(tmp_path / "outbox.db"))
    outbox = outbox_ctx.__enter__()

    core = DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events, decision_archive=archive)

    ledger_ctx = SqliteLedger(str(tmp_path / "ledger.db"))
    ledger = ledger_ctx.__enter__()

    # Create a decision, then run recovery with a clock far in the future so it becomes stale.
    state = WorldStateV1(1, {}, {}, {}, {}, int(time.time() * 1000), user_id="u1")
    env = core.optimize(state)
    archive.put(env)

    outbox.enqueue_once(
        decision_id=str(env.decision.decision_id),
        correlation_id=str(env.decision.correlation_id),
        action=str(env.decision.action),
        payload_json="{}",
    )

    # Guard clock forces DecisionExpired.
    future_now = int(env.decision.issued_at_ms) + int(MAX_REPLAY_MS) + 10_000
    guard = RuntimeGuard(keyring, ledger, schemas, event_log=events, clock=_Clock(future_now))

    handlers = ActionHandlerRegistry()
    handlers.register("send_message@v1", lambda payload, effects, env: None)
    executor = RuntimeExecutor(
        guard,
        handlers,
        events,
        policy_registry=preg,
        decision_core=core,
        outbox=outbox,
        decision_archive=archive,
    )

    # Must NOT raise.
    n = recover_pending(executor=executor, outbox=outbox, archive=archive, limit=100)
    assert n == 0

    # Quarantined: should no longer be pending/delivering.
    assert outbox.status(str(env.decision.decision_id)) in {"dead", "delivered"}

    ledger_ctx.__exit__(None, None, None)
    archive_ctx.__exit__(None, None, None)
    outbox_ctx.__exit__(None, None, None)

import json
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
from runtime.guard import RuntimeGuard
from runtime.handlers import ActionHandlerRegistry
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.platform.ledger.sqlite_ledger import SqliteLedger
from runtime.platform.outbox.sqlite_outbox import SqliteOutbox


class PolicyA:
    id = "p@v1"

    def propose(self, state):
        return type("O", (), {"action": "send_message@v1", "payload": {"user_id": "u1", "text": "hi", "tenant_id": "tenant-1"}})()


def test_runtime_executor_persists_reliability_checkpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    schemas = SchemaRegistry()
    schemas.register(
        "send_message@v1",
        1,
        DecisionSchema(required={"user_id", "text"}, optional={"tenant_id"}, field_types={"user_id": str, "text": str, "tenant_id": str}),
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
    guard = RuntimeGuard(keyring, ledger, schemas, event_log=events)

    handlers = ActionHandlerRegistry()
    handlers.register("send_message@v1", lambda payload, effects, env: {"ok": True, "echo": payload["text"]})

    executor = RuntimeExecutor(guard, handlers, events, policy_registry=preg, decision_core=core, outbox=outbox, decision_archive=archive)

    state = WorldStateV1(1, {}, {}, {}, {}, int(time.time() * 1000), user_id="u1")
    env = core.optimize(state)

    result = executor.execute(env)
    assert result.ok is True
    assert result.output['effect_delivery']['decision_id'] == str(env.decision.decision_id)
    assert result.output['effect_delivery']['runtime_outbox_status'] == 'delivered'

    checkpoint_path = tmp_path / "data" / "reliability" / "execution_checkpoints.jsonl"
    assert checkpoint_path.exists()
    rows = [json.loads(line) for line in checkpoint_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    stages = [row["stage"] for row in rows if row["run_id"] == str(env.decision.decision_id)]
    assert "request" in stages
    assert "decision" in stages
    assert "execution" in stages
    assert "completed" in stages

    ledger_ctx.__exit__(None, None, None)
    archive_ctx.__exit__(None, None, None)
    outbox_ctx.__exit__(None, None, None)

from __future__ import annotations

from contextlib import ExitStack

import pytest

from core.ai.decision_core import DecisionCore
from core.ai.policy_registry import PolicyRegistry
from core.ai.schema_registry import DecisionSchema, SchemaRegistry
from core.ai.snapshot_store import MemorySnapshotStore
from core.events.log import EventLog
from core.learning.learning_system import LearningSystem
from core.policies.selector import PolicySelector
from core.security.keyring import Keyring
from runtime.executor import RuntimeExecutor
from runtime.guard import RuntimeGuard
from runtime.handlers import ActionHandlerRegistry
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.platform.ledger.sqlite_ledger import SqliteLedger
from runtime.platform.outbox.sqlite_outbox import SqliteOutbox
from runtime.self_driving_scheduler import tick_once


class DummyPolicy:
    id = "dummy@v1"

    def propose(self, state):
        return type("O", (), {"action": "noop@v1", "payload": {}})()


class MetaDeployPolicy:
    id = "policy_deployment@v1"

    def __init__(self, reg):
        self._reg = reg

    def propose(self, state):
        proposal = getattr(state, "deployment_proposal", None) or {}
        if proposal.get("kind") == "deploy":
            return type(
                "O",
                (),
                {"action": "deploy_policy@v1", "payload": {"candidate_policy_id": proposal["candidate_policy_id"], "rollout_pct": int(proposal["rollout_pct"])}},
            )()
        return type("O", (), {"action": "noop@v1", "payload": {}})()


def test_self_driving_tick_executes_meta_deploy(tmp_path):
    preg = PolicyRegistry()
    preg.register(DummyPolicy())
    preg.register(MetaDeployPolicy(preg))

    selector = PolicySelector(preg)

    schemas = SchemaRegistry()
    schemas.register("noop@v1", 1, DecisionSchema(required=set(), optional=set(), field_types={}))
    schemas.register(
        "deploy_policy@v1",
        1,
        DecisionSchema(required={"candidate_policy_id", "rollout_pct"}, optional=set(), field_types={"candidate_policy_id": str, "rollout_pct": int}),
    )

    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    snapshots = MemorySnapshotStore()
    event_log = EventLog(MemoryEventStore(), tenant="default")

    core = DecisionCore(selector=selector, keyring=keyring, schema_registry=schemas, snapshot_store=snapshots, event_log=event_log)

    handlers = ActionHandlerRegistry()
    handlers.register(
        "deploy_policy@v1",
        lambda payload, effects, env: effects.deploy_policy(
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
            candidate_policy_id=payload["candidate_policy_id"],
            rollout_pct=int(payload["rollout_pct"]),
        ),
    )

    learning = LearningSystem(min_samples=1)
    learning.observe_reward(policy_id=DummyPolicy.id, reward=1.0)

    with ExitStack() as stack:
        ledger = stack.enter_context(SqliteLedger(str(tmp_path / "ledger.db")))
        outbox = stack.enter_context(SqliteOutbox(str(tmp_path / "outbox.db")))
        guard = RuntimeGuard(keyring, ledger, schemas, event_log=event_log)

        executor = RuntimeExecutor(
            guard,
            handlers,
            event_log,
            policy_registry=preg,
            reward_engine=None,
            learning_system=None,
            decision_core=core,
            outbox=outbox,
            snapshot_store=snapshots,
            ledger=ledger,
        )

        # Canonical safety contract:
        # self-driving learning may propose deploy_policy@v1, but execution must
        # not bypass governance approvals. A policy deployment without approvals
        # is expected to be blocked by the decision safety gate.
        with pytest.raises(Exception) as exc_info:
            tick_once(learning_system=learning, decision_core=core, executor=executor)
        assert "insufficient_approvals" in str(exc_info.value)

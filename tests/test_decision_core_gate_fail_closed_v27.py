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
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _Policy:
    id = "p@v1"

    def propose(self, state):
        return type("O", (), {"action": "send_message@v1", "payload": {"user_id": "u1", "text": "hi"}})()


def _build_core():
    schemas = SchemaRegistry()
    schemas.register(
        "send_message@v1",
        1,
        DecisionSchema(required={"user_id", "text"}, optional=set(), field_types={"user_id": str, "text": str}),
    )
    registry = PolicyRegistry()
    registry.register(_Policy())
    selector = PolicySelector(registry)
    keyring = Keyring({"k1": {"secret": b"s1", "revoked": False}}, "k1")
    events = EventLog(MemoryEventStore(), tenant="default")
    return DecisionCore(selector, keyring, schemas, MemorySnapshotStore(), events), events


def _state(*, meta=None):
    return WorldStateV1(
        1, {}, {}, {}, {}, int(time.time() * 1000),
        tenant_id="default", user_id="u1", meta=dict(meta or {}),
    )


def test_decision_core_blocks_when_safety_gate_errors(monkeypatch):
    import application.decision_runtime.runtime as decision_runtime

    core, events = _build_core()

    def _boom(**kwargs):
        raise ValueError("gate exploded")

    monkeypatch.setattr(decision_runtime, "gate_action_or_raise", _boom)

    with pytest.raises(RuntimeError, match="DECISION_BLOCKED:action_safety_gate_error"):
        core.issue(_state())

    event_log = events
    rows = [e for e in event_log.iter_events() if e.get("event_type") == "decision_blocked"]
    assert rows
    assert rows[-1]["payload"]["reason"] == "action_safety_gate_error"


def test_decision_core_blocks_effectful_action_on_canonical_goal_conflict():
    core, events = _build_core()
    state = _state(
        meta={
            "canonical_goal": {
                "goal": {
                    "goal_id": "sales",
                    "metric": "revenue",
                    "baseline": 100.0,
                    "target": 120.0,
                },
                "constraints": {"guard_metrics": [], "evidence_only": True},
                "conflicts": {
                    "has_conflicts": True,
                    "goal_goal": [
                        {
                            "conflict_kind": "opposing_goal_direction",
                            "other_goal_id": "cost-cut",
                        }
                    ],
                    "goal_constraint": [],
                    "deterministic_only": True,
                },
            }
        }
    )

    with pytest.raises(RuntimeError, match="DECISION_BLOCKED:canonical_goal_conflict"):
        core.issue(state)

    rows = [e for e in events.iter_events() if e.get("event_type") == "decision_blocked"]
    assert rows
    assert rows[-1]["payload"]["reason"] == "canonical_goal_conflict"
    assert rows[-1]["payload"]["goal_id"] == "sales"
    assert rows[-1]["payload"]["goal_goal_conflict_count"] == 1

from __future__ import annotations

import time

from core.ai.decision_core import DecisionCore
from core.ai.policy_registry import PolicyRegistry
from core.ai.schema_registry import DecisionSchema, SchemaRegistry
from core.ai.snapshot_store import MemorySnapshotStore
from core.ai.world_state import WorldStateV1
from core.events.log import EventLog
from core.policies.selector import PolicySelector
from core.security.keyring import Keyring
from kernel.decision_crypto import verify_signed_material
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _Policy:
    id = "phase6@v1"

    def propose(self, state):
        return type(
            "_Proposal",
            (),
            {
                "action": "send_message@v1",
                "payload": {"user_id": "user-1", "text": "hello"},
            },
        )()


def _core() -> DecisionCore:
    schemas = SchemaRegistry()
    schemas.register(
        "send_message@v1",
        1,
        DecisionSchema(
            required={"user_id", "text"},
            optional=set(),
            field_types={"user_id": str, "text": str},
        ),
    )
    registry = PolicyRegistry()
    registry.register(_Policy())
    return DecisionCore(
        PolicySelector(registry),
        Keyring({"k1": {"secret": b"secret", "revoked": False}}, "k1"),
        schemas,
        MemorySnapshotStore(),
        EventLog(MemoryEventStore(), tenant="tenant-1"),
    )


def _state(*, goal_bound: bool) -> WorldStateV1:
    meta = {}
    if goal_bound:
        meta = {
            "goal_id": "goal-1",
            "canonical_goal": {
                "goal": {
                    "goal_id": "goal-1",
                    "metric": "profit",
                    "baseline": 100.0,
                    "target": 120.0,
                },
                "constraints": {
                    "guard_metrics": [],
                    "evidence_only": True,
                },
                "conflicts": {
                    "has_conflicts": False,
                    "goal_goal": [],
                    "goal_constraint": [],
                    "deterministic_only": True,
                },
            },
        }
    return WorldStateV1(
        1,
        {"user_id": "user-1", "tenant_id": "tenant-1"},
        {"channel": "headless"},
        {"business_id": "business-1"},
        {},
        int(time.time() * 1000),
        tenant_id="tenant-1",
        user_id="user-1",
        meta=meta,
    )


def test_formal_goal_bound_decision_uses_signed_v2_contract(monkeypatch) -> None:
    import application.decision_runtime.runtime as decision_runtime

    monkeypatch.setattr(
        decision_runtime,
        "gate_action_or_raise",
        lambda **kwargs: (True, "ok", {}),
    )
    env = _core().issue(_state(goal_bound=True))

    assert env.envelope_version == 2
    assert env.decision.envelope_version == 2
    contract = dict(env.decision.contract_v2 or {})
    assert contract["schema_version"] == 2
    assert contract["business_id"] == "business-1"
    assert contract["goal_id"] == "goal-1"
    assert contract["selected_option"]["option_id"] == "send_message@v1"
    assert contract["alternatives"] is None
    assert "alternatives:UNKNOWN" in contract["rationale"]["uncertainties"]
    assert env.decision.payload["goal_id"] == "goal-1"
    assert verify_signed_material(
        decision=env.decision,
        payload_hash_value=env.payload_hash,
        signature=env.signature,
        secret=b"secret",
        kid=env.kid,
    )


def test_non_goal_decision_remains_v1(monkeypatch) -> None:
    import application.decision_runtime.runtime as decision_runtime

    monkeypatch.setattr(
        decision_runtime,
        "gate_action_or_raise",
        lambda **kwargs: (True, "ok", {}),
    )
    env = _core().issue(_state(goal_bound=False))

    assert env.envelope_version == 1
    assert env.decision.envelope_version == 1
    assert env.decision.contract_v2 is None
    assert "goal_id" not in env.decision.payload

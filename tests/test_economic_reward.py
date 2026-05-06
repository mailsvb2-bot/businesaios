from __future__ import annotations

import time
import uuid

from core.ai.decision import Decision, DecisionEnvelope
from core.ai.snapshot_store import MemorySnapshotStore
from core.economics.brain import EconomicBrain, EconomicReward, GrowthPolicy, LTVEstimator, PricingPolicy
from core.events.log import EventLog
from core.reward.reward_engine import RewardEngine
from core.utils.canonical import canonical_json_bytes, payload_hash

from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _mk_env(*, snapshot_id: str):
    issued = int(time.time() * 1000)
    d = Decision(
        decision_id=str(uuid.uuid4()),
        issuer_id="test",
        issued_at_ms=issued,
        expires_at_ms=issued + 1000,
        policy_id="p@v1",
        action="send_message@v1",
        payload={"user_id": "u1", "text": "x"},
        snapshot_id=snapshot_id,
        state_hash="h",
        correlation_id="c",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    ph = payload_hash(d.payload)
    return DecisionEnvelope(decision=d, payload_hash=ph, signature="sig", kid="k1", envelope_version=1)


def test_reward_engine_prefers_governed_economic_reward_when_economy_present():
    snaps = MemorySnapshotStore()
    events = EventLog(MemoryEventStore(), tenant="default")

    # economy present => governed reward
    ws = {
        "schema_version": 1,
        "user": {},
        "session": {},
        "product": {},
        "economy": {"retention_prob": 0.5, "revenue": 10.0, "cost": 2.0},
        "timestamp_ms": 0,
        "user_id": "u1",
        "safe_mode": False,
        "deployment_proposal": None,
    }
    sid = "s1"
    snaps.put(sid, canonical_json_bytes(ws))

    brain = EconomicBrain(LTVEstimator(), PricingPolicy(), GrowthPolicy(), EconomicReward())
    re = RewardEngine(snapshot_store=snaps, economic_brain=brain, event_log=events)

    env = _mk_env(snapshot_id=sid)
    # Proof prerequisite (anti-gaming): reward forbidden without proof.
    events.emit(event_type="message_sent", source="tests", user_id="u1", decision_id=env.decision.decision_id, correlation_id="c", payload={"ok": True})
    r = re.observe(env, execution_output=None)

    # LTV = 0.5*(10-2)=4.0; pricing keep(0.0); growth hold? retention_prob=0.5 => hold(0.0)
    assert r == 4.0


def test_reward_engine_falls_back_to_money_reward_when_economy_missing():
    snaps = MemorySnapshotStore()
    events = EventLog(MemoryEventStore(), tenant="default")
    sid = "s2"
    ws = {
        "schema_version": 1,
        "user": {},
        "session": {},
        "product": {},
        "economy": None,
        "timestamp_ms": 0,
        "user_id": "u1",
        "safe_mode": False,
        "deployment_proposal": None,
    }
    snaps.put(sid, canonical_json_bytes(ws))

    brain = EconomicBrain(LTVEstimator(), PricingPolicy(), GrowthPolicy(), EconomicReward())
    re = RewardEngine(snapshot_store=snaps, economic_brain=brain, event_log=events, money_scale=0.01)

    issued = int(time.time() * 1000)
    d = Decision(
        decision_id=str(uuid.uuid4()),
        issuer_id="test",
        issued_at_ms=issued,
        expires_at_ms=issued + 1000,
        policy_id="p@v1",
        action="capture_payment@v1",
        payload={"user_id": "u1", "amount": 5000, "currency": "RUB"},
        snapshot_id=sid,
        state_hash="h",
        correlation_id="c",
        state_schema_version=1,
        action_schema_version=1,
        envelope_version=1,
    )
    ph = payload_hash(d.payload)
    env = DecisionEnvelope(decision=d, payload_hash=ph, signature="sig", kid="k1", envelope_version=1)

    # Proof prerequisite
    events.emit(event_type="payment_captured", source="tests", user_id="u1", decision_id=env.decision.decision_id, correlation_id="c", payload={"ok": True})

    r = re.observe(env, execution_output=None)
    assert r == 50.0

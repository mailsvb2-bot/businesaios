from __future__ import annotations

from threading import Event, Thread

import pytest

from core.governance.guards.policy_update_gate import (
    PolicyUpdateGate,
    PolicyUpdateGateError,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _FailingStore(MemoryEventStore):
    def __init__(self) -> None:
        super().__init__()
        self.fail_event_type: str | None = None

    def append_event(self, event: dict):
        if event.get("event_type") == self.fail_event_type:
            raise RuntimeError("write failed")
        super().append_event(event)


class _BlockingStore(MemoryEventStore):
    def __init__(self) -> None:
        super().__init__()
        self.started = Event()
        self.release = Event()

    def append_event(self, event: dict):
        if event.get("event_type") == "policy_update_applied@v1":
            self.started.set()
            assert self.release.wait(timeout=5)
        super().append_event(event)


def _prepare(
    gate: PolicyUpdateGate,
    *,
    update_id: str = "u1",
    now_ms: int = 1_000,
    payload: dict | None = None,
) -> None:
    gate.propose(
        tenant_id="tenant-a",
        domain="pricing",
        update_id=update_id,
        payload=payload or {"nested": {"value": 1}},
        now_ms=now_ms,
    )
    gate.approve(
        tenant_id="tenant-a",
        domain="pricing",
        update_id=update_id,
        now_ms=now_ms + 1,
    )


def test_gate_replays_only_its_own_tenant_scoped_events() -> None:
    store = MemoryEventStore()
    store.extend(
        [
            {
                "event_id": "forged-proposed",
                "tenant_id": "tenant-a",
                "user_id": "attacker",
                "source": "untrusted",
                "event_type": "policy_update_proposed@v1",
                "timestamp_ms": 10,
                "payload": {
                    "domain": "pricing",
                    "update_id": "forged",
                    "created_ms": 10,
                    "update_payload": {"price": 1},
                },
            },
            {
                "event_id": "forged-approved",
                "tenant_id": "tenant-a",
                "user_id": "attacker",
                "source": "untrusted",
                "event_type": "policy_update_approved@v1",
                "timestamp_ms": 11,
                "payload": {
                    "domain": "pricing",
                    "update_id": "forged",
                    "created_ms": 10,
                    "update_payload": {"price": 1},
                },
            },
        ]
    )
    gate = PolicyUpdateGate(event_store=store, cooldown_ms=0)

    with pytest.raises(PolicyUpdateGateError, match="Unknown update"):
        gate.claim_for_apply(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="forged",
            now_ms=20,
        )

    writer = PolicyUpdateGate(event_store=store, cooldown_ms=0)
    _prepare(writer, update_id="valid", now_ms=30, payload={"price": 2})
    replay = PolicyUpdateGate(event_store=store, cooldown_ms=0)
    assert replay.claim_for_apply(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="valid",
        now_ms=40,
    ) == {"price": 2}


def test_state_changes_only_after_durable_event_append() -> None:
    store = _FailingStore()
    gate = PolicyUpdateGate(event_store=store, cooldown_ms=0)

    store.fail_event_type = "policy_update_proposed@v1"
    with pytest.raises(RuntimeError, match="write failed"):
        gate.propose(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="u1",
            payload={"price": 1},
            now_ms=100,
        )
    assert gate._pending == {}

    store.fail_event_type = None
    gate.propose(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        payload={"price": 1},
        now_ms=101,
    )
    store.fail_event_type = "policy_update_approved@v1"
    with pytest.raises(RuntimeError, match="write failed"):
        gate.approve(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="u1",
            now_ms=102,
        )
    assert gate._pending["tenant-a:pricing:u1"].approved is False

    store.fail_event_type = None
    gate.approve(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=103,
    )
    store.fail_event_type = "policy_update_applied@v1"
    with pytest.raises(RuntimeError, match="write failed"):
        gate.claim_for_apply(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="u1",
            now_ms=104,
        )
    assert "tenant-a:pricing:u1" in gate._pending
    assert gate._last_apply_ms == {}

    store.fail_event_type = None
    assert gate.claim_for_apply(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=105,
    ) == {"price": 1}


def test_claim_is_single_winner_per_gate_instance() -> None:
    store = _BlockingStore()
    gate = PolicyUpdateGate(event_store=store, cooldown_ms=0)
    _prepare(gate, now_ms=200, payload={"price": 7})
    outcomes: list[object] = []

    def claim() -> None:
        try:
            outcomes.append(
                gate.claim_for_apply(
                    tenant_id="tenant-a",
                    domain="pricing",
                    update_id="u1",
                    now_ms=210,
                )
            )
        except Exception as exc:  # noqa: BLE001 - asserted below
            outcomes.append(exc)

    first = Thread(target=claim)
    second = Thread(target=claim)
    first.start()
    assert store.started.wait(timeout=5)
    second.start()
    store.release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert sum(isinstance(item, dict) for item in outcomes) == 1
    errors = [item for item in outcomes if isinstance(item, PolicyUpdateGateError)]
    assert len(errors) == 1
    assert "Unknown update" in str(errors[0])
    applied = [
        event
        for event in store
        if event.get("event_type") == "policy_update_applied@v1"
    ]
    assert len(applied) == 1


def test_payload_is_snapshotted_and_returned_defensively() -> None:
    store = MemoryEventStore()
    gate = PolicyUpdateGate(event_store=store, cooldown_ms=0)
    source = {"nested": {"value": 1}}
    gate.propose(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        payload=source,
        now_ms=300,
    )
    source["nested"]["value"] = 999
    gate.approve(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=301,
    )
    claimed = gate.claim_for_apply(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=302,
    )
    assert claimed == {"nested": {"value": 1}}
    claimed["nested"]["value"] = 555
    assert store[-1]["payload"]["update_payload"] == {"nested": {"value": 1}}


def test_cooldown_is_replayed_and_scoped_by_tenant_and_domain() -> None:
    store = MemoryEventStore()
    first = PolicyUpdateGate(event_store=store, cooldown_ms=500)
    _prepare(first, update_id="u1", now_ms=1_000, payload={"price": 1})
    first.claim_for_apply(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=1_010,
    )

    second = PolicyUpdateGate(event_store=store, cooldown_ms=500)
    _prepare(second, update_id="u2", now_ms=1_100, payload={"price": 2})
    with pytest.raises(PolicyUpdateGateError, match="wait 410 ms"):
        second.claim_for_apply(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="u2",
            now_ms=1_100,
        )
    assert second.claim_for_apply(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u2",
        now_ms=1_510,
    ) == {"price": 2}

    other = PolicyUpdateGate(event_store=store, cooldown_ms=500)
    other.propose(
        tenant_id="tenant-b",
        domain="pricing",
        update_id="u3",
        payload={},
        now_ms=1_100,
    )
    other.approve(
        tenant_id="tenant-b",
        domain="pricing",
        update_id="u3",
        now_ms=1_101,
    )
    assert other.claim_for_apply(
        tenant_id="tenant-b",
        domain="pricing",
        update_id="u3",
        now_ms=1_102,
    ) == {}


def test_validation_idempotent_approval_and_store_rebind_fail_closed() -> None:
    with pytest.raises(ValueError, match="cooldown_ms"):
        PolicyUpdateGate(cooldown_ms=-1)

    gate = PolicyUpdateGate(cooldown_ms=0)
    for field, kwargs in (
        ("tenant_id", {"tenant_id": ""}),
        ("domain", {"domain": ""}),
        ("update_id", {"update_id": ""}),
    ):
        values = {
            "tenant_id": "tenant-a",
            "domain": "pricing",
            "update_id": "u1",
            "payload": {},
            "now_ms": 1,
        }
        values.update(kwargs)
        with pytest.raises(PolicyUpdateGateError, match=field):
            gate.propose(**values)

    with pytest.raises(PolicyUpdateGateError, match="payload must be a mapping"):
        gate.propose(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="u1",
            payload="bad",  # type: ignore[arg-type]
            now_ms=1,
        )
    for value in (True, 0, -1, "bad"):
        with pytest.raises(PolicyUpdateGateError, match="now_ms"):
            gate.propose(
                tenant_id="tenant-a",
                domain="pricing",
                update_id="u1",
                payload={},
                now_ms=value,  # type: ignore[arg-type]
            )

    store = MemoryEventStore()
    gate.bind_event_store(store)
    gate.propose(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        payload={},
        now_ms=10,
    )
    gate.approve(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=11,
    )
    approval_count = sum(
        event.get("event_type") == "policy_update_approved@v1" for event in store
    )
    gate.approve(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=12,
    )
    assert sum(
        event.get("event_type") == "policy_update_approved@v1" for event in store
    ) == approval_count

    gate.bind_event_store(None)
    with pytest.raises(PolicyUpdateGateError, match="Unknown update"):
        gate.claim_for_apply(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="u1",
            now_ms=13,
        )


class _Uncopyable:
    def __deepcopy__(self, memo):
        raise RuntimeError("no copy")


class _ScriptedStore:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def append(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(self, **kwargs):
        event_type = kwargs.get("event_type")
        for event in self.events:
            if not isinstance(event, dict) or event.get("event_type") == event_type:
                yield event


def test_replay_validation_and_helper_edges() -> None:
    canonical = {
        "event_id": "canonical",
        "tenant_id": "tenant-a",
        "user_id": "system",
        "source": "governance_policy_gate",
        "event_type": "policy_update_proposed@v1",
        "timestamp_ms": "100",
        "payload": {
            "domain": "pricing",
            "update_id": "u1",
            "created_ms": "bad",
            "update_payload": {"price": 1},
        },
    }
    events: list[object] = [
        "not-a-dict",
        {**canonical, "event_id": "wrong-tenant", "tenant_id": "tenant-b"},
        {**canonical, "event_id": "wrong-update", "payload": {**canonical["payload"], "update_id": "other"}},
        {**canonical, "event_id": "bad-proposal", "timestamp_ms": True, "payload": {**canonical["payload"], "update_payload": []}},
        canonical,
        {
            **canonical,
            "event_id": "bad-approval",
            "event_type": "policy_update_approved@v1",
            "timestamp_ms": 101,
            "payload": {**canonical["payload"], "update_payload": "bad"},
        },
        {
            **canonical,
            "event_id": "approval",
            "event_type": "policy_update_approved@v1",
            "timestamp_ms": 102,
            "payload": {**canonical["payload"], "created_ms": False, "update_payload": None},
        },
        {
            **canonical,
            "event_id": "stale-applied",
            "event_type": "policy_update_applied@v1",
            "timestamp_ms": 50,
        },
        {
            **canonical,
            "event_id": "other-domain-applied",
            "event_type": "policy_update_applied@v1",
            "timestamp_ms": "bad",
            "payload": {**canonical["payload"], "domain": "other"},
        },
    ]
    store = _ScriptedStore(events)
    gate = PolicyUpdateGate(event_store=store, cooldown_ms=0)
    gate.approve(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=103,
    )
    assert gate.claim_for_apply(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=104,
    ) == {"price": 1}

    assert PolicyUpdateGate._resolve_iter_events(None) is None
    assert PolicyUpdateGate._resolve_iter_events(object()) is None
    assert PolicyUpdateGate._event_timestamp_ms({"timestamp_ms": True}) == 0
    assert PolicyUpdateGate._event_timestamp_ms({"timestamp_ms": "bad"}) == 0
    assert PolicyUpdateGate._event_timestamp_ms({"timestamp_ms": -5}) == 0
    assert PolicyUpdateGate._payload_timestamp_ms(True, fallback=7) == 7
    assert PolicyUpdateGate._payload_timestamp_ms("bad", fallback=8) == 8
    assert PolicyUpdateGate._payload_timestamp_ms(0, fallback=9) == 9
    assert PolicyUpdateGate._payload_timestamp_ms(10, fallback=9) == 10
    assert not PolicyUpdateGate._matches_update(
        {"tenant_id": "tenant-a", "source": "governance_policy_gate", "payload": []},
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
    )


def test_unknown_unapproved_unbound_and_uncopyable_paths() -> None:
    gate = PolicyUpdateGate(cooldown_ms=0)
    with pytest.raises(PolicyUpdateGateError, match="Unknown update"):
        gate.approve(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="missing",
            now_ms=1,
        )

    gate.propose(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        payload=None,  # type: ignore[arg-type]
    )
    with pytest.raises(PolicyUpdateGateError, match="not approved"):
        gate.claim_for_apply(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="u1",
            now_ms=2,
        )
    gate.approve(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=3,
    )
    assert gate.claim_for_apply(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u1",
        now_ms=4,
    ) == {}

    with pytest.raises(PolicyUpdateGateError, match="safely copyable"):
        gate.propose(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="u2",
            payload={"value": _Uncopyable()},
            now_ms=5,
        )


def test_store_change_and_cache_disappearance_fail_closed(monkeypatch) -> None:
    store_a = MemoryEventStore()
    store_b = MemoryEventStore()
    writer = PolicyUpdateGate(event_store=store_a, cooldown_ms=0)
    writer.propose(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="approve-rebind",
        payload={},
        now_ms=10,
    )

    gate = PolicyUpdateGate(event_store=store_a, cooldown_ms=0)
    original_load_pending = gate._load_pending

    def load_then_rebind(**kwargs):
        result = original_load_pending(**kwargs)
        gate.bind_event_store(store_b)
        return result

    monkeypatch.setattr(gate, "_load_pending", load_then_rebind)
    with pytest.raises(PolicyUpdateGateError, match="changed during approval"):
        gate.approve(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="approve-rebind",
            now_ms=11,
        )

    gate = PolicyUpdateGate(event_store=store_a, cooldown_ms=0)
    monkeypatch.setattr(
        gate,
        "_load_pending",
        lambda **kwargs: __import__(
            "core.governance.guards.policy_update_gate",
            fromlist=["PendingUpdate"],
        ).PendingUpdate("tenant-a", "pricing", "ghost", 1, False, {}),
    )
    with pytest.raises(PolicyUpdateGateError, match="Unknown update"):
        gate.approve(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="ghost",
            now_ms=12,
        )

    writer = PolicyUpdateGate(event_store=store_a, cooldown_ms=0)
    _prepare(writer, update_id="claim-rebind", now_ms=20, payload={})
    gate = PolicyUpdateGate(event_store=store_a, cooldown_ms=0)
    original_load_pending = gate._load_pending

    def load_claim_then_rebind(**kwargs):
        result = original_load_pending(**kwargs)
        gate.bind_event_store(store_b)
        return result

    monkeypatch.setattr(gate, "_load_pending", load_claim_then_rebind)
    with pytest.raises(PolicyUpdateGateError, match="changed during claim"):
        gate.claim_for_apply(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="claim-rebind",
            now_ms=22,
        )

    gate = PolicyUpdateGate(cooldown_ms=0)
    _prepare(gate, update_id="vanish", now_ms=30, payload={})

    def remove_pending(**kwargs):
        gate._pending.clear()
        return 0

    monkeypatch.setattr(gate, "_load_last_apply_ms", remove_pending)
    with pytest.raises(PolicyUpdateGateError, match="Unknown update"):
        gate.claim_for_apply(
            tenant_id="tenant-a",
            domain="pricing",
            update_id="vanish",
            now_ms=32,
        )


def test_replay_cache_is_not_written_after_store_rebind() -> None:
    store = MemoryEventStore()
    writer = PolicyUpdateGate(event_store=store, cooldown_ms=0)
    _prepare(writer, update_id="u-cache", now_ms=500, payload={})
    writer.claim_for_apply(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u-cache",
        now_ms=502,
    )
    writer.propose(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u-pending",
        payload={},
        now_ms=503,
    )

    gate = PolicyUpdateGate(event_store=None, cooldown_ms=0)
    pending = gate._load_pending(
        tenant_id="tenant-a",
        domain="pricing",
        update_id="u-pending",
        store=store,
    )
    assert pending is not None
    assert gate._pending == {}
    assert gate._load_last_apply_ms(
        tenant_id="tenant-a",
        domain="pricing",
        store=store,
    ) == 502
    assert gate._last_apply_ms == {}

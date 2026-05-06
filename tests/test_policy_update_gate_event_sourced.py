from __future__ import annotations

import pytest

from core.governance.guards.policy_update_gate import PolicyUpdateGate, PolicyUpdateGateError
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_policy_update_gate_persists_cooldown_and_pending_state() -> None:
    es = MemoryEventStore()
    gate = PolicyUpdateGate(cooldown_ms=1000, event_store=es)

    gate.propose(tenant_id="t1", domain="ads.rl.suggest", update_id="u1", payload={"x": 1}, now_ms=100)
    gate.approve(tenant_id="t1", domain="ads.rl.suggest", update_id="u1", now_ms=110)
    assert gate.claim_for_apply(tenant_id="t1", domain="ads.rl.suggest", update_id="u1", now_ms=120) == {"x": 1}

    reloaded = PolicyUpdateGate(cooldown_ms=1000, event_store=es)
    reloaded.propose(tenant_id="t1", domain="ads.rl.suggest", update_id="u2", payload={"x": 2}, now_ms=150)
    reloaded.approve(tenant_id="t1", domain="ads.rl.suggest", update_id="u2", now_ms=160)
    with pytest.raises(PolicyUpdateGateError, match="Cooldown active"):
        reloaded.claim_for_apply(tenant_id="t1", domain="ads.rl.suggest", update_id="u2", now_ms=200)

    events = list(es.iter_events(tenant_id="t1", start_ms=0, end_ms=None, event_type="policy_update_applied@v1"))
    assert events
    assert events[0]["payload"]["domain"] == "ads.rl.suggest"


def test_policy_update_gate_reloads_approved_pending_update() -> None:
    es = MemoryEventStore()
    gate = PolicyUpdateGate(cooldown_ms=1000, event_store=es)
    gate.propose(tenant_id="t1", domain="ads.autopilot", update_id="u3", payload={"ok": True}, now_ms=100)
    gate.approve(tenant_id="t1", domain="ads.autopilot", update_id="u3", now_ms=120)

    fresh = PolicyUpdateGate(cooldown_ms=1000, event_store=es)
    assert fresh.claim_for_apply(tenant_id="t1", domain="ads.autopilot", update_id="u3", now_ms=130) == {"ok": True}

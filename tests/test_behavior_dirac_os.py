from __future__ import annotations

import time

from core.behavior.complex4 import Complex4
from core.behavior.dirac_behavior import DiracBehaviorModel
from core.telemetry.behavior_read_model import behavior_snapshot


def test_dirac_behavior_observables_bounded_and_deterministic():
    model = DiracBehaviorModel()
    psi0 = Complex4.zeros().renormalize(target_norm=1.0)
    now_ms = int(time.time() * 1000)
    events = [
        {"timestamp_ms": now_ms - 9000, "event_type": "ui_click", "payload": {"rage": 0}},
        {"timestamp_ms": now_ms - 7000, "event_type": "offer_shown", "payload": {}},
        {"timestamp_ms": now_ms - 5000, "event_type": "offer_clicked", "payload": {}},
        {"timestamp_ms": now_ms - 3000, "event_type": "payment_failed", "payload": {}},
        {"timestamp_ms": now_ms - 1000, "event_type": "payment_success", "payload": {}},
    ]

    psi_a, obs_a = model.evolve(psi=psi0, events=events, now_ms=now_ms, context={"anti": 0.0})
    psi_b, obs_b = model.evolve(psi=psi0, events=events, now_ms=now_ms, context={"anti": 0.0})

    assert psi_a.re == psi_b.re
    assert psi_a.im == psi_b.im
    assert obs_a == obs_b

    for k in [
        "engagement_score",
        "hesitation_score",
        "purchase_probability",
        "fatigue_index",
        "trust_index",
        "coherence",
        "anti",
    ]:
        v = float(obs_a.get(k))
        assert 0.0 <= v <= 1.0


def test_behavior_snapshot_includes_os_metrics_memory_store():
    # minimal in-memory store compatible with latest_events
    class _Store:
        def __init__(self, evs):
            self._evs = list(evs)

        def latest_events(self, *, tenant_id="default", user_id=None, event_type=None, event_types=None, limit=10):
            out = [e for e in self._evs if (user_id is None or e.get("user_id") == user_id)]
            if event_type:
                out = [e for e in out if e.get("event_type") == event_type]
            elif event_types:
                out = [e for e in out if e.get("event_type") in set(event_types)]
            out = sorted(out, key=lambda x: int(x.get("timestamp_ms") or 0), reverse=True)
            return out[: int(limit)]

    now_ms = int(time.time() * 1000)
    evs = [
        {"timestamp_ms": now_ms - 4000, "event_type": "behavior_telemetry", "payload": {"schema": "behavior_telemetry@v1", "kind": "callback"}, "user_id": "u1"},
        {"timestamp_ms": now_ms - 3000, "event_type": "offer_shown", "payload": {}, "user_id": "u1"},
        {"timestamp_ms": now_ms - 2000, "event_type": "offer_clicked", "payload": {}, "user_id": "u1"},
        {"timestamp_ms": now_ms - 1000, "event_type": "payment_success", "payload": {}, "user_id": "u1"},
    ]
    store = _Store(evs)
    snap = behavior_snapshot(store, tenant_id="default", user_id="u1", limit=50, lookback_days=30)

    assert "engagement_score" in snap
    assert "trust_index" in snap
    assert "purchase_probability" in snap
    assert "org" in snap
    assert 0.0 <= float(snap["engagement_score"]) <= 1.0

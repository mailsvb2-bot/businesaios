from __future__ import annotations

import time

from core.growth.ads.rl.contracts import AdsRLOptSpec
from core.growth.ads.rl.observer import observe_tick_once
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class DummyRL:
    def __init__(self):
        self.calls = []

    def observe(self, *, tenant_id: str, user_id, spec, policy_id: str, action, meta):
        self.calls.append({"tenant_id": tenant_id, "spec": spec, "policy_id": policy_id, "action": action, "meta": meta})
        return {"status": "ok"}


def test_ads_rl_observer_attaches_reward_from_import_event() -> None:
    es = MemoryEventStore()
    rl = DummyRL()
    tid = "t1"
    now = int(time.time() * 1000)

    spec = AdsRLOptSpec(
        platform="meta",
        campaign_id="c1",
        daily_budgets=[10.0, 12.0],
        bid_caps=[0.5],
        cpa_targets=[3.0],
        creatives=["cr1"],
        audiences=["a1"],
        objectives=["sales"],
    )

    es.append_event(
        {
            "tenant_id": tid,
            "user_id": "u1",
            "source": "ads_rl",
            "event_type": "ads_rl_suggested@v1",
            "timestamp_ms": now - 10_000,
            "payload": {
                "policy_id": "p1",
                "campaign_id": "c1",
                "platform": "meta",
                "action_key": "k",
                "action": {"campaign_id": "c1", "daily_budget": 12.0},
                "meta": {"spec": spec.to_json()},
            },
        }
    )

    es.append_event(
        {
            "event_id": "e_import_1",
            "tenant_id": tid,
            "user_id": "",
            "source": "ads_import",
            "event_type": "ads_metrics_imported",
            "timestamp_ms": now - 1000,
            "payload": {
                "ref": {"platform": "meta", "object_type": "campaign", "object_id": "c1", "day": "2026-03-04"},
                "metrics": {"spend": 1.0, "revenue": 2.0},
            },
        }
    )

    res = observe_tick_once(tenant_id=tid, event_store=es, rl_service=rl, max_import_events=50)
    assert res.ok
    assert res.processed == 1
    assert len(rl.calls) == 1

    # checkpoint persisted
    ck = list(es.iter_events(tenant_id=tid, start_ms=0, event_type="ads_rl_observer_checkpoint@v1"))
    assert len(ck) == 1

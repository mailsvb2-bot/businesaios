from __future__ import annotations

from core.pricing.logging import emit_pricing_decision
from core.pricing.rl_picker import RLPricingConfig, choose_price_rub
from ml.ope import evaluate_ips_snips
from ml.pricing_dataset import build_pricing_dataset
from ml.pricing_trainer import target_propensity_from_tabular, train_tabular_policy
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _ev(*, tenant_id: str, event_type: str, ts: int, user_id: str, payload: dict):
    return {
        "tenant_id": tenant_id,
        "event_id": f"{event_type}-{user_id}-{ts}",
        "timestamp_ms": ts,
        "user_id": user_id,
        "event_type": event_type,
        "payload": payload,
        "source": "test",
    }


def test_rl_picker_returns_probs_and_propensity_offer_outcome_signals():
    store = MemoryEventStore()
    tid = "t1"
    arm = "offer_30_14900"
    now = 2_000_000_000_000

    # 3 impressions at 600, 2 at 700
    for i in range(3):
        ts = now - 10_000 + i
        store.append_event(_ev(tenant_id=tid, event_type="offer_shown", ts=ts, user_id=f"u{i}", payload={"arm": arm, "price_rub": 600, "segment": "tg"}))
        store.append_event(_ev(tenant_id=tid, event_type="offer_outcome", ts=ts +1000, user_id=f"u{i}", payload={"shown_event_id": f"offer_shown-u{i}-{ts}", "arm": arm, "price_rub": 600, "success": True}))

    for j in range(2):
        ts = now - 9_000 + j
        store.append_event(_ev(tenant_id=tid, event_type="offer_shown", ts=ts, user_id=f"v{j}", payload={"arm": arm, "price_rub": 700, "segment": "tg"}))
        store.append_event(_ev(tenant_id=tid, event_type="offer_outcome", ts=ts +1000, user_id=f"v{j}", payload={"shown_event_id": f"offer_shown-v{j}-{ts}", "arm": arm, "price_rub": 700, "success": False}))

    cfg = RLPricingConfig(enabled=True, lookback_days=30, grid_radius_pct=0.5, grid_step_rub=100, temperature=0.5)
    price, dbg = choose_price_rub(store, tenant_id=tid, offer_arm=arm, base_price_rub=600, cfg=cfg, now_ms=now, context_key="tg")

    assert price in set(dbg.get("candidates") or [])
    assert dbg.get("propensity") is not None
    assert 0.0 < float(dbg["propensity"]) <= 1.0

    probs = dbg.get("probs")
    assert isinstance(probs, dict)
    s = sum(float(v) for v in probs.values())
    assert abs(s - 1.0) < 1e-6


def test_pricing_decision_event_and_dataset_and_ope_roundtrip():
    store = MemoryEventStore()
    tid = "t1"
    arm = "offer_30_14900"
    now = 2_000_000_000_000

    # Create a logged decision and an outcome
    cfg = RLPricingConfig(enabled=True, lookback_days=30, grid_radius_pct=0.5, grid_step_rub=100, temperature=1.0)

    # Evidence so picker has stats
    ts0 = now - 50_000
    store.append_event(_ev(tenant_id=tid, event_type="offer_shown", ts=ts0, user_id="u", payload={"arm": arm, "price_rub": 600, "segment": "tg"}))
    store.append_event(_ev(tenant_id=tid, event_type="offer_outcome", ts=ts0 +1000, user_id="u", payload={"shown_event_id": f"offer_shown-u-{ts0}", "arm": arm, "price_rub": 600, "success": True}))

    chosen, dbg = choose_price_rub(store, tenant_id=tid, offer_arm=arm, base_price_rub=600, cfg=cfg, now_ms=now, context_key="tg")

    emit_pricing_decision(
        store,
        tenant_id=tid,
        user_id="u2",
        offer_arm=arm,
        base_price_rub=600,
        chosen_price_rub=chosen,
        policy_id=str(dbg.get("policy_id") or "pricing_rl_v2"),
        propensity=float(dbg.get("propensity") or 1.0),
        segment="tg",
        candidates=list(dbg.get("candidates") or []),
        probs=dict(dbg.get("probs") or {}),
        timestamp_ms=now - 1_000,
        extra={"test": True},
    )

    # Outcome for that user
    store.append_event(_ev(tenant_id=tid, event_type="offer_outcome", ts=now, user_id="u2", payload={"shown_event_id": "x", "arm": arm, "price_rub": chosen, "success": True}))

    ds = build_pricing_dataset(store, tenant_id=tid, start_ts_ms=now - 100_000, end_ts_ms=now +1, join_window_ms=10_000)
    assert ds.rows, "dataset should not be empty"

    tr = train_tabular_policy(ds.rows)
    target = target_propensity_from_tabular(tr.policy)
    rep = evaluate_ips_snips(ds.rows, target_propensity=target)

    assert rep.n >= 1
    assert rep.w_sum >= 0.0

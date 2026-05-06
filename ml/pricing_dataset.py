from __future__ import annotations

"""Logged bandit dataset builder for RL pricing.

We build a deterministic table from the canonical event stream:
- pricing_decision_logged (context + candidates/probabilities + chosen)
- offer_outcome (reward proxy tied to offer_shown, independent)

Because pricing decisions happen before outcomes, we join by (user_id, offer_arm,
chosen_price_rub) within a time window, preferring the nearest future outcome.

This yields a stable dataset usable for:
- offline policy training
- off-policy evaluation (IPS / SNIPS)

IMPORTANT:
- This module is offline-only. It must not depend on platform storage details.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from contracts.event_store import iter_events_strict


@dataclass(frozen=True)
class PricingRow:
    ts_ms: int
    tenant_id: str
    user_id: str
    offer_arm: str
    segment: str
    base_price_rub: int
    chosen_price_rub: int
    propensity: float
    reward: float
    policy_id: str


@dataclass(frozen=True)
class PricingDataset:
    snapshot_id: str
    start_ts_ms: int
    end_ts_ms: int
    rows: List[Dict[str, Any]]



def _stable_hash(rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> str:
    import hashlib
    import json

    raw = json.dumps({"meta": meta, "rows": rows}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_pricing_dataset(
    store: Any,
    *,
    tenant_id: str,
    start_ts_ms: int,
    end_ts_ms: int,
    join_window_ms: int = 24 * 3600 * 1000,
) -> PricingDataset:
    """Build a deterministic dataset snapshot for pricing RL."""

    if not callable(getattr(store, "iter_events", None)):
        return PricingDataset(snapshot_id=_stable_hash([], {"empty": True}), start_ts_ms=int(start_ts_ms), end_ts_ms=int(end_ts_ms), rows=[])

    # Load pricing decisions
    decisions: List[Dict[str, Any]] = []
    for ev in iter_events_strict(store, tenant_id=str(tenant_id), start_ms=int(start_ts_ms), end_ms=int(end_ts_ms), event_type="pricing_decision_logged"):
        if not isinstance(ev, dict):
            continue
        p = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        try:
            decisions.append(
                {
                    "ts_ms": int(ev.get("timestamp_ms") or 0),
                    "user_id": str(ev.get("user_id") or "").strip(),
                    "offer_arm": str(p.get("offer_arm") or "").strip(),
                    "segment": str(p.get("segment") or "").strip(),
                    "base_price_rub": int(p.get("base_price_rub") or 0),
                    "chosen_price_rub": int(p.get("chosen_price_rub") or 0),
                    "propensity": float(p.get("propensity") or 0.0),
                    "policy_id": str(p.get("policy_id") or "").strip(),
                }
            )
        except Exception:
            continue

    # Load offer outcomes (reward proxy)
    outcomes: List[Dict[str, Any]] = []
    for ev in iter_events_strict(store, tenant_id=str(tenant_id), start_ms=int(start_ts_ms), end_ms=int(end_ts_ms), event_type="offer_outcome"):
        if not isinstance(ev, dict):
            continue
        p = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        try:
            outcomes.append(
                {
                    "ts_ms": int(ev.get("timestamp_ms") or 0),
                    "user_id": str(ev.get("user_id") or "").strip(),
                    "offer_arm": str(p.get("arm") or p.get("offer_arm") or "").strip(),
                    "price_rub": int(p.get("price_rub") or 0),
                    "success": bool(p.get("success")),
                }
            )
        except Exception:
            continue

    decisions.sort(key=lambda r: (int(r["ts_ms"]), r["user_id"], r["offer_arm"]))
    outcomes.sort(key=lambda r: (int(r["ts_ms"]), r["user_id"], r["offer_arm"]))

    # Index outcomes by (user_id, offer_arm) for forward scan
    by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for o in outcomes:
        k = (str(o["user_id"]), str(o["offer_arm"]))
        by_key.setdefault(k, []).append(o)

    rows: List[Dict[str, Any]] = []
    for d in decisions:
        if not d["user_id"] or not d["offer_arm"] or d["chosen_price_rub"] <= 0:
            continue
        if not (float(d["propensity"]) > 0.0):
            continue
        k = (str(d["user_id"]), str(d["offer_arm"]))
        cand = by_key.get(k) or []
        # find nearest outcome after decision within join window
        reward = 0.0
        ts0 = int(d["ts_ms"])
        for o in cand:
            ts1 = int(o["ts_ms"])
            if ts1 < ts0:
                continue
            if ts1 > ts0 + int(join_window_ms):
                break
            # optionally require matching price when present
            if int(o.get("price_rub") or 0) > 0 and int(o.get("price_rub") or 0) != int(d["chosen_price_rub"]):
                continue
            reward = float(int(d["chosen_price_rub"])) if bool(o.get("success")) else 0.0
            break

        rows.append(
            {
                "ts_ms": int(d["ts_ms"]),
                "tenant_id": str(tenant_id),
                "user_id": str(d["user_id"]),
                "offer_arm": str(d["offer_arm"]),
                "segment": str(d.get("segment") or ""),
                "base_price_rub": int(d["base_price_rub"]),
                "chosen_price_rub": int(d["chosen_price_rub"]),
                "propensity": float(d["propensity"]),
                "reward": float(reward),
                "policy_id": str(d.get("policy_id") or ""),
            }
        )

    rows.sort(key=lambda r: (int(r["ts_ms"]), r["user_id"], r["offer_arm"]))
    meta = {"tenant_id": str(tenant_id), "start_ts_ms": int(start_ts_ms), "end_ts_ms": int(end_ts_ms), "join_window_ms": int(join_window_ms)}
    sid = _stable_hash(rows, meta)
    return PricingDataset(snapshot_id=sid, start_ts_ms=int(start_ts_ms), end_ts_ms=int(end_ts_ms), rows=rows)

from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple
from collections.abc import Iterable


def now_ms() -> int:
    return int(time.time() * 1000)


def iter_events(
    event_store: Any,
    *,
    tenant_id: str,
    start_ms: int,
    end_ms: int,
    event_type: str,
) -> Iterable[dict[str, Any]]:
    it = getattr(event_store, "iter_events", None)
    if not callable(it):
        return ()
    return it(tenant_id=str(tenant_id), start_ms=int(start_ms), end_ms=int(end_ms), event_type=str(event_type))


def hours(ms: int) -> float:
    return float(ms) / 3600_000.0


def compute_burst_count_with_decay(
    trigger_ts_desc: list[int],
    *,
    base_cooldown_hours: int,
    max_cooldown_hours: int,
) -> tuple[int, int, list[dict[str, Any]]]:
    base_h = int(max(0, base_cooldown_hours))
    max_h = int(max(0, max_cooldown_hours))
    if base_h <= 0:
        return 0, 0, []
    if max_h <= 0:
        max_h = base_h

    ts = [int(x) for x in trigger_ts_desc if int(x) > 0]
    ts.sort(reverse=True)
    if not ts:
        return 0, 0, []

    accepted: list[int] = [ts[0]]
    evidence: list[dict[str, Any]] = [{"ts_ms": int(ts[0]), "accepted": True, "reason": "newest"}]
    burst = 1
    eff = int(min(base_h, max_h))

    for nxt in ts[1:]:
        prev = accepted[-1]
        gap_h = hours(int(prev) - int(nxt))
        quiet_h = float(max(base_h, int(eff) / 2))
        if gap_h <= quiet_h:
            accepted.append(int(nxt))
            burst += 1
            mult = 1 if burst <= 1 else (2 ** (burst - 1))
            eff = int(min(int(base_h) * int(mult), int(max_h)))
            evidence.append({"ts_ms": int(nxt), "accepted": True, "gap_hours": float(gap_h), "quiet_period_hours": float(quiet_h)})
        else:
            evidence.append(
                {
                    "ts_ms": int(nxt),
                    "accepted": False,
                    "gap_hours": float(gap_h),
                    "quiet_period_hours": float(quiet_h),
                    "reason": "quiet_period_exceeded",
                }
            )
            break
    return int(burst), int(eff), evidence


def cooldown_state(
    event_store: Any,
    *,
    tenant_id: str,
    offer_arm: str,
    context_key: str,
    now_ms: int,
    base_cooldown_hours: int,
    max_cooldown_hours: int,
    backoff_lookback_hours: int,
    decay_enabled: bool,
) -> dict[str, Any]:
    base_h = int(max(0, base_cooldown_hours))
    max_h = int(max(0, max_cooldown_hours))
    lookback_h = int(max(0, backoff_lookback_hours))
    if base_h <= 0:
        return {"active": False, "effective_cooldown_hours": 0, "recent_triggers": 0, "last_trigger_ms": None, "burst_count": 0, "decay_enabled": bool(decay_enabled)}
    if max_h <= 0:
        max_h = base_h
    if lookback_h <= 0:
        lookback_h = max(base_h, 24)

    start_ms = int(now_ms) - lookback_h * 3600 * 1000
    end_ms = int(now_ms)
    ctx = str(context_key or "").strip()
    ts_list: list[int] = []
    for ev in iter_events(event_store, tenant_id=str(tenant_id), start_ms=int(start_ms), end_ms=int(end_ms), event_type="pricing_stoploss_triggered"):
        try:
            p = ev.get("payload") or {}
            arm = str(p.get("offer_arm") or p.get("arm") or "")
            if arm != str(offer_arm):
                continue
            seg = str(p.get("segment") or p.get("traffic_source") or p.get("utm_source") or p.get("channel") or "").strip()
            if ctx and seg != ctx:
                continue
            ts = int(ev.get("timestamp_ms") or 0)
            if ts > 0:
                ts_list.append(int(ts))
        except Exception:
            continue
    if not ts_list:
        return {"active": False, "effective_cooldown_hours": 0, "recent_triggers": 0, "last_trigger_ms": None, "burst_count": 0, "decay_enabled": bool(decay_enabled)}

    last_ms = int(max(ts_list))
    evidence: list[dict[str, Any]] = []
    if bool(decay_enabled):
        burst_n, eff, evidence = compute_burst_count_with_decay(sorted(ts_list, reverse=True), base_cooldown_hours=int(base_h), max_cooldown_hours=int(max_h))
    else:
        n = int(max(0, len(ts_list)))
        mult = 1 if n <= 1 else (2 ** (n - 1))
        eff = int(min(int(base_h) * int(mult), int(max_h)))
        burst_n = int(n)
    active = bool(eff > 0 and int(now_ms) - int(last_ms) <= eff * 3600 * 1000)
    return {
        "active": bool(active),
        "effective_cooldown_hours": int(eff),
        "recent_triggers": int(len(ts_list)),
        "last_trigger_ms": int(last_ms),
        "burst_count": int(burst_n),
        "decay_enabled": bool(decay_enabled),
        "burst_evidence": evidence[:10],
    }

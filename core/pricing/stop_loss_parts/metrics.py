from __future__ import annotations

from typing import Any
from collections.abc import Mapping

from .cooldown import iter_events


def collect_trials(
    event_store: Any,
    *,
    tenant_id: str,
    offer_arm: str,
    start_ms: int,
    end_ms: int,
    context_key: str,
) -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    ctx = str(context_key or "").strip()
    for ev in iter_events(event_store, tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, event_type="tariff_selected"):
        try:
            p = ev.get("payload") or {}
            tariff = str(p.get("tariff") or "")
            if tariff != str(offer_arm):
                continue
            seg = str(p.get("segment") or p.get("traffic_source") or p.get("utm_source") or p.get("channel") or "").strip()
            if ctx and seg != ctx:
                continue
            uid = str(ev.get("user_id") or "")
            amount = int(p.get("amount") or 0)
            ts = int(ev.get("timestamp_ms") or 0)
            if uid and amount > 0 and ts > 0:
                trials.append({"user_id": uid, "amount": amount, "ts": ts})
        except Exception:
            continue
    return trials


def collect_payments_index(event_store: Any, *, tenant_id: str, start_ms: int, end_ms: int) -> dict[str, list[int]]:
    payments_by_user: dict[str, list[int]] = {}
    for ev in iter_events(event_store, tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, event_type="payment_captured"):
        try:
            uid = str(ev.get("user_id") or "")
            ts = int(ev.get("timestamp_ms") or 0)
            if uid and ts > 0:
                payments_by_user.setdefault(uid, []).append(int(ts))
        except Exception:
            continue
    for uid in list(payments_by_user.keys()):
        payments_by_user[uid] = sorted(payments_by_user[uid])
    return payments_by_user


def stats_trials_successes(trials: list[dict[str, Any]], payments_by_user: Mapping[str, list[int]], *, window_ms: int) -> dict[int, tuple[int, int]]:
    stats: dict[int, tuple[int, int]] = {}
    for t in trials:
        uid = str(t.get("user_id") or "")
        amount = int(t.get("amount") or 0)
        ts0 = int(t.get("ts") or 0)
        if not uid or amount <= 0 or ts0 <= 0:
            continue
        trials_n, succ_n = stats.get(amount, (0, 0))
        trials_n += 1
        paid = False
        for pts in (payments_by_user.get(uid) or []):
            if pts < ts0:
                continue
            if pts > ts0 + int(window_ms):
                break
            paid = True
            break
        if paid:
            succ_n += 1
        stats[amount] = (int(trials_n), int(succ_n))
    return stats


def conv_and_rev_per_trial(trials_n: int, succ_n: int, price: int) -> tuple[float, float]:
    if trials_n <= 0:
        return 0.0, 0.0
    conv = float(succ_n) / float(trials_n)
    return conv, float(price) * float(conv)

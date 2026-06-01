from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.pricing.rl.event_reader import (
    collect_offer_outcomes_index,
    collect_offer_shown,
    collect_payments_index_legacy,
    collect_trials_legacy,
)


def stats_trials_successes_legacy(trials: list[dict[str, Any]], payments_by_user: dict[str, list[int]], *, window_ms: int) -> tuple[dict[int, tuple[int, int]], int]:
    stats: dict[int, tuple[int, int]] = {}
    succ_total = 0
    for t in trials:
        uid = str(t["user_id"])
        amount = int(t["amount"])
        ts0 = int(t["ts"])
        trials_n, succ_n = stats.get(amount, (0, 0))
        trials_n += 1
        paid = False
        for pts in payments_by_user.get(uid) or []:
            if pts < ts0:
                continue
            if pts > ts0 + window_ms:
                break
            paid = True
            break
        if paid:
            succ_n += 1
            succ_total += 1
        stats[amount] = (trials_n, succ_n)
    return stats, succ_total


def collect_pricing_evidence(*, event_store: Any, tenant_id: str, offer_arm: str, start_ms: int, end_ms: int, window_ms: int, context_key: str = "") -> tuple[dict[int, tuple[int, int]], dict[str, Any]]:
    debug: dict[str, Any] = {}
    shown_all = collect_offer_shown(event_store, tenant_id=str(tenant_id), offer_arm=str(offer_arm), start_ms=start_ms, end_ms=end_ms)
    if context_key:
        shown = [s for s in shown_all if str(s.get("segment") or "").strip() == context_key]
        debug["trials_all"] = int(len(shown_all))
    else:
        shown = shown_all
    if shown:
        outcomes = collect_offer_outcomes_index(event_store, tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms)
        stats: dict[int, tuple[int, int]] = {}
        succ_total = 0
        for s in shown:
            price = int(s.get("amount") or 0)
            if price <= 0:
                continue
            trials_n, succ_n = stats.get(price, (0, 0))
            trials_n += 1
            if outcomes.get(str(s.get("event_id") or "").strip()) is True:
                succ_n += 1
                succ_total += 1
            stats[price] = (trials_n, succ_n)
        debug.update({"signal": "offer_shown/offer_outcome", "trials": int(len(shown)), "successes": int(succ_total), "observed_prices": int(len(stats))})
        return stats, debug

    trials_all = collect_trials_legacy(event_store, tenant_id=str(tenant_id), offer_arm=str(offer_arm), start_ms=start_ms, end_ms=end_ms)
    if context_key:
        trials = [t for t in trials_all if str(t.get("segment") or "").strip() == context_key]
        debug["trials_all"] = int(len(trials_all))
    else:
        trials = trials_all
    debug.update({"signal": "tariff_selected/payment_captured", "trials": int(len(trials))})
    stats = {}
    succ_total = 0
    if trials:
        payments_by_user = collect_payments_index_legacy(event_store, tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms)
        stats, succ_total = stats_trials_successes_legacy(trials, payments_by_user, window_ms=window_ms)
    debug.update({"successes": int(succ_total), "observed_prices": int(len(stats))})
    return stats, debug

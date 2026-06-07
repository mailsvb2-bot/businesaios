from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from core.admin.ai_pricing_support import resolve_now_ms


@dataclass(frozen=True)
class PricingSuggestion:
    plan_id: int
    base_price: int
    suggested_price: int
    samples: int
    successes: int
    window_hours: int
    method: str
    note: str


def _now_ms() -> int:
    return int(time.time() * 1000)


def _round_price(p: float, step: int = 10) -> int:
    step = max(1, int(step))
    return int(round(float(p) / step) * step)


def _require_tenant_id(tenant_id: str) -> str:
    tid = str(tenant_id or "").strip()
    if not tid:
        raise ValueError(
            "tenant_id is required (strict). Propagate from BootContext/ProductContext; do not rely on defaults."
        )
    return tid


def suggest_price_for_plan(
    event_store: Any,
    *,
    tenant_id: str,
    plan_id: int,
    base_price: int,
    window_hours: int = 24,
    lookback_days: int = 30,
    grid_radius: float = 0.30,
    grid_step: int = 10,
    prior_alpha: float = 1.0,
    prior_beta: float = 19.0,
    now_ms: int | None = None,
) -> PricingSuggestion:
    """Suggest a new price using only local event_store data.

    IMPORTANT: this function NEVER applies pricing. It only suggests.

    We estimate conversion as:
      P(pay | select) within window_hours after tariff_selected.

    For each observed price point, we compute a Bayesian posterior mean:
      E[p] = (succ + alpha) / (trials + alpha + beta)

    Then we evaluate candidate prices in a grid around base_price and choose the
    argmax of expected revenue:
      revenue(p) = p * E[conv(p)]

    If there is no data, we fallback to a conservative suggestion (=base_price).
    """
    try:
        pid = int(plan_id)
    except Exception:
        pid = 0
    base = int(max(1, base_price))

    tid = _require_tenant_id(tenant_id)

    end_ms = resolve_now_ms(explicit_now_ms=now_ms, fallback_now_ms=_now_ms)
    start_ms = end_ms - int(lookback_days) * 24 * 3600 * 1000
    window_ms = int(window_hours) * 3600 * 1000
    # Collect selections for this plan.
    selections: list[dict[str, Any]] = []
    it_sel = event_store.iter_events(tenant_id=tid, start_ms=start_ms, end_ms=end_ms, event_type="tariff_selected")
    for ev in it_sel:
        try:
            pl = ev.get("payload") or {}
            if int(pl.get("plan_id") or -1) != pid:
                continue
            uid = str(ev.get("user_id") or "")
            amount = int(pl.get("amount") or 0)
            ts = int(ev.get("timestamp_ms") or 0)
            if not uid or amount <= 0 or ts <= 0:
                continue
            selections.append({"user_id": uid, "amount": amount, "ts": ts})
        except Exception:
            continue

    if not selections:
        return PricingSuggestion(
            plan_id=pid,
            base_price=base,
            suggested_price=base,
            samples=0,
            successes=0,
            window_hours=int(window_hours),
            method="bayes_grid_v1",
            note="Недостаточно данных (нет tariff_selected для этого тарифа). Оставляю текущую цену.",
        )

    # Build a quick lookup of payments per user in the lookback window.
    payments_by_user: dict[str, list[int]] = {}
    it_pay = event_store.iter_events(tenant_id=tid, start_ms=start_ms, end_ms=end_ms, event_type="payment_captured")
    for ev in it_pay:
        try:
            uid = str(ev.get("user_id") or "")
            ts = int(ev.get("timestamp_ms") or 0)
            if not uid or ts <= 0:
                continue
            payments_by_user.setdefault(uid, []).append(ts)
        except Exception:
            continue

    for uid in list(payments_by_user.keys()):
        payments_by_user[uid].sort()

    # Aggregate trials/successes per observed amount.
    stats: dict[int, tuple[int, int]] = {}  # amount -> (trials, successes)
    succ_total = 0
    for s in selections:
        uid = s["user_id"]
        amount = int(s["amount"])
        ts0 = int(s["ts"])
        trials, succ = stats.get(amount, (0, 0))
        trials += 1
        paid = False
        plist = payments_by_user.get(uid) or []
        # Linear scan is ok for small local stores; keep simple & deterministic.
        for pts in plist:
            if pts < ts0:
                continue
            if pts > ts0 + window_ms:
                break
            paid = True
            break
        if paid:
            succ += 1
            succ_total += 1
        stats[amount] = (trials, succ)

    # If we have no payments at all, don't "invent" higher prices.
    if succ_total == 0:
        return PricingSuggestion(
            plan_id=pid,
            base_price=base,
            suggested_price=base,
            samples=len(selections),
            successes=0,
            window_hours=int(window_hours),
            method="bayes_grid_v1",
            note="Есть выбор тарифа, но нет оплат в окне. Цена оставлена без изменений.",
        )

    # Helper: posterior mean conversion for a price point.
    def conv_mean(price: int) -> float:
        trials, succ = stats.get(int(price), (0, 0))
        return (succ + prior_alpha) / (trials + prior_alpha + prior_beta)

    # Candidate grid around base_price.
    lo = max(10, int(round(base * (1.0 - float(grid_radius)))))
    hi = int(round(base * (1.0 + float(grid_radius))))
    candidates = list(range(_round_price(lo, grid_step), _round_price(hi, grid_step) + grid_step, int(grid_step)))
    if base not in candidates:
        candidates.append(base)
        candidates.sort()

    # If we don't have observations for a candidate, we interpolate by nearest observed price.
    observed_prices = sorted(stats.keys())
    def conv_est(price: int) -> float:
        if price in stats:
            return conv_mean(price)
        if not observed_prices:
            return conv_mean(base)
        # nearest neighbor
        nearest = min(observed_prices, key=lambda x: abs(int(x) - int(price)))
        return conv_mean(nearest)

    best_p = base
    best_rev = -1.0
    for p in candidates:
        c = conv_est(p)
        rev = float(p) * float(c)
        if rev > best_rev:
            best_rev = rev
            best_p = int(p)

    note = (
        f"Оценка конверсии: P(pay|select) в окне {int(window_hours)}ч. "
        f"Наблюдений: {len(selections)}, оплат: {succ_total}. "
        f"Рекомендация выбрана по max(price * E[conv])."
    )
    return PricingSuggestion(
        plan_id=pid,
        base_price=base,
        suggested_price=int(best_p),
        samples=len(selections),
        successes=int(succ_total),
        window_hours=int(window_hours),
        method="bayes_grid_v1",
        note=note,
    )

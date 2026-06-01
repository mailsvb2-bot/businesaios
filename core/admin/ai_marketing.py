from __future__ import annotations

"""Deterministic "AI" helpers for admin buttons.

We do NOT call external LLMs from runtime.
Instead we:
- derive features from the event-store read models
- use the governed EconomicBrain (pricing/growth policies)
- generate stable text variants (A/B) based on hashing

This keeps the system:
- reproducible
- sovereign (DecisionCore decides; runtime only executes)
- easy to test
"""

import hashlib
from typing import Any, Dict, List

from config.admin_marketing_policy import DEFAULT_ADMIN_MARKETING_POLICY, AdminMarketingPolicy
from core.economics.brain import EconomicBrain
from core.economics.types import EconomicState


def _stable_choice(key: str, options: list[str]) -> str:
    if not options:
        return ""
    h = hashlib.sha256(key.encode("utf-8")).digest()
    idx = int.from_bytes(h[:4], "big") % len(options)
    return options[idx]


def _retention_prob(metrics: dict[str, Any]) -> float:
    retention = metrics.get("retention") if isinstance(metrics.get("retention"), dict) else {}
    users = max(1, int(retention.get("users") or 1))
    active_2d = int(retention.get("active_2d") or 0)
    return max(float(0), min(float(1), float(active_2d) / float(users)))


def _avg_plan_price(plans: list[dict[str, Any]]) -> float:
    prices: list[float] = []
    for plan in plans:
        try:
            price = float(plan.get("price") or 0)
        except Exception:
            continue
        if price > 0:
            prices.append(price)
    return (sum(prices) / float(len(prices))) if prices else float(0)


def recommend_prices(*, brain: EconomicBrain, metrics: dict[str, Any], plans: list[dict[str, Any]], policy: AdminMarketingPolicy = DEFAULT_ADMIN_MARKETING_POLICY) -> dict[str, Any]:
    """Return deterministic price recommendations.

    Output:
      {"ok": True, "items": [{"title", "price", "why"}, ...]}

    We *do not* mutate tariffs here.
    """
    if not isinstance(metrics, dict):
        return {"ok": False, "reason": "INVALID_METRICS"}
    if not isinstance(plans, list):
        return {"ok": False, "reason": "INVALID_PLANS"}

    retention_prob = _retention_prob(metrics)
    funnel = metrics.get("funnel") if isinstance(metrics.get("funnel"), dict) else {}
    paid = int(funnel.get("payment_succeeded") or funnel.get("payment_captured") or 0)
    revenue = float(paid) * float(_avg_plan_price(plans))
    state = EconomicState(
        retention_prob=float(retention_prob),
        revenue=float(revenue),
        cost=float(0),
    )
    signals = brain.signals(state)
    pricing = signals.pricing
    action = str(getattr(pricing, "kind", "keep"))
    value = float(getattr(pricing, "value", float(0)))

    why = "Сигналы смешанные → держим цену."
    if action == "discount":
        why = "Удержание низкое → пробуем скидку, чтобы увеличить вовлечённость."
    elif action == "upsell":
        why = "Удержание высокое → можно аккуратно поднять цену (upsell)."

    items: list[dict[str, Any]] = []
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        title = str(plan.get("title") or plan.get("code") or "Тариф")
        try:
            base = int(plan.get("price") or 0)
        except Exception:
            continue
        if base <= 0:
            continue
        adjustment = max(policy.pricing.min_discount_floor_pct, min(policy.pricing.max_discount_floor_pct, value))
        if action == "discount":
            new_price = int(max(policy.pricing.min_price_major_units, round(base * (1 - adjustment))))
        elif action == "upsell":
            new_price = int(round(base * (1 + adjustment)))
        else:
            new_price = int(base)
        items.append({"title": title, "price": int(new_price), "why": why})

    return {"ok": True, "items": items, "meta": {"action": action, "value": value, "retention_prob": retention_prob}}


def generate_copy_variants(*, step_key: str, product_name: str = DEFAULT_ADMIN_MARKETING_POLICY.copy.default_product_name, policy: AdminMarketingPolicy = DEFAULT_ADMIN_MARKETING_POLICY) -> dict[str, str]:
    """Generate deterministic A/B copy variants for a funnel step."""
    step_key = str(step_key or "").strip().lower()
    templates = policy.copy.step_templates
    opts = tuple(templates.get(step_key) or policy.copy.fallback_templates)

    a = _stable_choice(f"{step_key}:a", opts)
    b = _stable_choice(f"{step_key}:b", list(reversed(opts)))
    a = a.format(product=product_name)
    b = b.format(product=product_name)
    if a.strip() == b.strip():
        b = (b + " 🙌").strip()
    return {"a": a, "b": b}

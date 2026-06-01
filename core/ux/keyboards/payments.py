from __future__ import annotations

"""Tariff, subscription and payment keyboards."""

from typing import Any, Dict, List

from core.ux.callbacks import CB_GIFT_CREATE, CB_GIFT_MENU, CB_MENU_MAIN, CB_SUB_MENU

from .common import mk


def kb_gift_menu() -> dict[str, Any]:
    return mk(
        [
            [{"text": "🎁 Создать подарочную ссылку", "callback_data": CB_GIFT_CREATE}],
            [{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}],
        ]
    )


def kb_tariffs(plans: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[dict[str, str]]] = []
    for p in plans:
        try:
            if not p.get("is_active", True):
                continue
            plan_id = int(p.get("plan_id"))
            title = str(p.get("title") or "").strip()[:64]
            price = int(p.get("price") or 0)
            if plan_id <= 0 or price <= 0 or not title:
                continue
            rows.append([{"text": f"{title} ({price} ₽)", "callback_data": f"sub:buy:{plan_id}:{price}"}])
        except Exception:
            continue
    if not rows:
        rows = [[{"text": "⚠️ Тарифы недоступны", "callback_data": CB_SUB_MENU}]]
    rows.append([{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}])
    return mk(rows)


def kb_sub(prices: dict[str, int]) -> dict[str, Any]:
    order = [
        ("Утро — 5 дней", "sub:morning:5"),
        ("Утро — 20 дней", "sub:morning:20"),
        ("Вечер — 5 дней", "sub:evening:5"),
        ("Вечер — 20 дней", "sub:evening:20"),
        ("Утро+Вечер — 5 дней", "sub:both:5"),
        ("Утро+Вечер — 20 дней", "sub:both:20"),
    ]
    rows: list[list[dict[str, str]]] = []
    for title, cb in order:
        price = prices.get(title)
        rows.append([{"text": f"{title} — {(str(price) + ' ₽') if price is not None else '? ₽'}", "callback_data": cb}])
    rows.append([{"text": "⬅️ Назад", "callback_data": CB_MENU_MAIN}])
    return mk(rows)


def kb_pay_selected() -> dict[str, Any]:
    return mk(
        [
            [{"text": "💳 Оплатить выбранный тариф", "callback_data": "pay:selected"}],
            [{"text": "⬅️ Назад", "callback_data": CB_SUB_MENU}],
        ]
    )

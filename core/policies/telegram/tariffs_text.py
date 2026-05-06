from __future__ import annotations

from typing import Any, Dict


def scope_hint(scope: str) -> str:
    s = (scope or "").strip().lower()
    if s == "morning":
        return "Утро"
    if s == "evening":
        return "Вечер"
    if s == "both":
        return "Утро+Вечер"
    return s or "Тариф"


def build_plan_confirmation_text(plan: Dict[str, Any]) -> str:
    title = str(plan.get("title") or "Тариф").strip()
    scope = scope_hint(str(plan.get("scope") or plan.get("plan_code") or ""))
    days = int(plan.get("days") or 0) if str(plan.get("days") or "").strip() else 0
    price = int(plan.get("price") or 0)
    desc = str(plan.get("description") or "").strip()
    schedule = str(plan.get("schedule") or "").strip()
    terms = str(plan.get("terms_short") or "").strip()

    lines = [f"✅ Вы выбрали тариф: {title}", ""]
    parts = []
    if scope:
        parts.append(scope)
    if days:
        parts.append(f"{days} дней")
    if parts:
        lines.append(" • ".join(parts))
    if price > 0:
        lines.append(f"Цена: {price} ₽")
    lines.append("")
    if desc:
        lines.append(desc)
        lines.append("")
    if days:
        lines.append(f"Длительность: {days} дней")
        lines.append("")
    lines.append("Расписание:")
    lines.append(schedule if schedule else "По выбранному ритму (утро/вечер).")
    lines.append("")
    lines.append("Условия:")
    lines.append(terms if terms else "Оплата разовая. Доступ выдаётся автоматически после успешной оплаты.")
    lines.append("")
    lines.append("Нажмите «Оплатить выбранный тариф», чтобы перейти к оплате.")
    return "\n".join(lines)

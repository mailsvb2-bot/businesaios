"""Canonical tenant-scoped admin analytics read projection.

Reuses the existing core.admin.read_model over the same event_store that
business_ops_summary@v1 already receives from the canonical handler wiring.
"""
from __future__ import annotations

from contracts.clientplatform_admin_analytics import ADMIN_ANALYTICS_ROUTES
from core.admin import read_model


def render_admin_analytics(*, event_store, tenant_id: str, route: str, now_ms: int | None = None) -> str:
    if route not in ADMIN_ANALYTICS_ROUTES:
        raise ValueError("unsupported_admin_analytics_route")
    if not tenant_id or tenant_id == "unknown":
        raise ValueError("admin_analytics_tenant_required")

    if route == "admin:segments":
        s = read_model.segments_summary(event_store, tenant_id=tenant_id, days=30, now_ms=now_ms)
        return (
            "🧲 Сегменты (30д/7д)\n\n"
            f"Новые сегодня: {s['new_users']}\n"
            f"Активные 7д: {s['active_users_7d']}\n"
            f"Плательщики 30д: {s['payers_30d']}\n"
            f"Доступ выдан 30д: {s['granted_30d']}"
        )
    if route == "admin:ab":
        s = read_model.ab_offers_summary(event_store, tenant_id=tenant_id, days=30, now_ms=now_ms)
        return (
            "🧪 A/B-тесты предложений (30д)\n\n"
            f"Сгенерировано вариантов: {s['variants_set']}\n"
            f"Выбрано вариантов: {s['variants_chosen']}"
        )
    if route == "admin:giftshare":
        s = read_model.giftshare_summary(event_store, tenant_id=tenant_id, days=30, now_ms=now_ms)
        return (
            "🎁 Подарки и рекомендации (30д)\n\n"
            f"Переходы по приглашениям: {s['share_clicked']}\n"
            f"Отправлено подарков: {s['gift_sent']}"
        )

    s = read_model.funnel2_report(event_store, tenant_id=tenant_id, days=7, now_ms=now_ms)
    counts, rates = s["counts"], s["rates_pct_from_view"]
    lines = ["🧲 Воронка 2.0 (7 дней)", ""]
    for key, label in (
        ("tariffs_viewed", "Просмотр тарифов"),
        ("tariff_selected", "Выбор тарифа"),
        ("payment_created", "Создание оплаты"),
        ("payment_captured", "Оплата успешна"),
        ("access_granted", "Доступ выдан"),
        ("audio_sent", "Первая отправка"),
    ):
        ratio = 100 if key == "tariffs_viewed" else rates.get(key, 0)
        lines.append(f"{label}: {counts.get(key, 0)} ({ratio}%)")
    return "\n".join(lines)

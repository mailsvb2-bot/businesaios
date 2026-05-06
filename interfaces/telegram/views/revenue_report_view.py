from __future__ import annotations

from core.contracts.revenue_report import RevenueReport


def _pct(x: float) -> str:
    return f"{x*100:.1f}%"


def render_revenue_report(r: RevenueReport) -> str:
    lines: list[str] = []
    lines.append(f"📈 Revenue Report за {r.day.isoformat()}")
    lines.append("")
    lines.append(f"Показы офферов: {r.impressions}")
    lines.append(f"Клики: {r.clicks} (CTR {_pct(r.ctr)})")
    lines.append(f"Покупки: {r.purchases_success} (CR {_pct(r.cr)})")
    if r.purchases_failed:
        lines.append(f"Ошибки оплаты: {r.purchases_failed}")
    lines.append(f"Выручка: {r.revenue:.2f}")
    lines.append("")
    if r.top_offer_id:
        lines.append(f"🏆 Лучший оффер: {r.top_offer_id} (+{r.top_offer_revenue:.2f})")
        lines.append("")
    lines.append(f"✅ Next Best Action: {r.next_best_action_title}")
    lines.append(r.next_best_action_text)
    lines.append("")
    lines.append("🛠 Авто-подсказка оффера: /suggest (сделаю конкретный diff)")
    lines.append("")
    lines.append("🚀 Хочешь ускорить? Нажми: /boost (статус) или открой меню → Boost.")
    return "\n".join(lines)
